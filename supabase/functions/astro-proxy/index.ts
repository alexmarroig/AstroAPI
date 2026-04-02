import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type, x-user-id, x-signature, x-signature-ts",
  "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
};

// Cache for resolved timezones (timezone+date -> tz_offset_minutes)
const tzCache = new Map<string, number>();

// Dev-mode logging
const isDev = Deno.env.get("ENVIRONMENT") !== "production";
const proxySecret = Deno.env.get("PROXY_SHARED_SECRET") ?? "";

function devLog(message: string, data?: unknown) {
  if (isDev) {
    console.log(`[astro-proxy] ${message}`, data ? JSON.stringify(data) : "");
  }
}

function toTodayIso(): string {
  return new Date().toISOString().split("T")[0];
}

function base64UrlEncode(bytes: ArrayBuffer): string {
  const bin = String.fromCharCode(...new Uint8Array(bytes));
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

async function signUser(userId: string, ts: string): Promise<string> {
  const keyData = new TextEncoder().encode(proxySecret);
  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    keyData,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );

  const data = new TextEncoder().encode(`${userId}:${ts}`);
  const sig = await crypto.subtle.sign("HMAC", cryptoKey, data);
  return base64UrlEncode(sig);
}

function sanitizeBaseUrl(raw: string): string {
  const trimmed = raw.trim().replace(/\/+$/, "");
  if (/\/v\d+($|\/)/i.test(trimmed)) {
    console.warn(`[astro-proxy] ASTRO_API_BASE_URL parece conter prefixo de rota: ${trimmed}`);
  }
  return trimmed;
}

/**
 * Validate JWT and return user ID
 */
async function validateAuth(req: Request): Promise<{ userId: string; error?: Response }> {
  const authHeader = req.headers.get("Authorization");

  if (!authHeader?.startsWith("Bearer ")) {
    return {
      userId: "",
      error: new Response(
        JSON.stringify({ detail: "Token de autenticação não fornecido" }),
        { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      ),
    };
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const supabaseAnonKey = Deno.env.get("SUPABASE_ANON_KEY");

  if (!supabaseUrl || !supabaseAnonKey) {
    console.error("[astro-proxy] Supabase secrets not configured");
    return {
      userId: "",
      error: new Response(
        JSON.stringify({ detail: "Configuração de autenticação incompleta" }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      ),
    };
  }

  const supabase = createClient(supabaseUrl, supabaseAnonKey, {
    global: { headers: { Authorization: authHeader } },
  });

  const token = authHeader.replace("Bearer ", "");
  const { data, error } = await supabase.auth.getClaims(token);

  if (error || !data?.claims) {
    devLog("Auth failed", error?.message);
    return {
      userId: "",
      error: new Response(
        JSON.stringify({ detail: "Token inválido ou expirado" }),
        { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      ),
    };
  }

  const userId = data.claims.sub as string;
  devLog(`Auth validated for user: ${userId}`);

  return { userId };
}

/**
 * Check if endpoint requires extended timeout (AI/heavy processing)
 */
function needsExtendedTimeout(path: string): boolean {
  const slowPaths = [
    "/v1/ai/cosmic-chat",
    "/api/chat/astral-oracle",
    "/v1/interpretation/natal",
    "/v1/synastry/compare",
    "/v1/synastry/deep",
    "/v1/synastry/timing",
    "/v1/forecast/personal",
    "/v1/solar-return/calculate",
    "/v1/solar-return/timeline",
    "/v1/insights/",
  ];
  return slowPaths.some(p => path.startsWith(p));
}

/**
 * Single function for all backend requests with proper headers
 */
async function proxyFetch(
  baseUrl: string,
  apiKey: string,
  path: string,
  method: string,
  body: unknown | undefined,
  userId: string,
  requestId: string,
  normalizationApplied: boolean
): Promise<Response> {
  const url = `${baseUrl.replace(/\/+$/, "")}${path}`;
  const timeout = needsExtendedTimeout(path) ? 45000 : 15000;
  const ts = new Date().toISOString();
  const signature = proxySecret ? await signUser(userId, ts) : null;

  devLog(`${method} ${url} (timeout: ${timeout}ms)`);
  devLog(`User: ${userId}`);
  if (body) {
    devLog(`Body keys: ${Object.keys(body as Record<string, unknown>).join(", ")}`);
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      method,
      headers: {
        "Authorization": `Bearer ${apiKey}`,
        "X-User-Id": userId,
        ...(signature ? { "X-Signature": signature, "X-Signature-Ts": ts } : {}),
        "Content-Type": "application/json",
      },
      body: method === "GET" ? undefined : JSON.stringify(body ?? {}),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);
    const text = await response.text();

    devLog(`upstream_response`, {
      request_id: requestId,
      method,
      path,
      upstream_status: response.status,
      normalized: normalizationApplied,
    });
    if (response.status >= 400) {
      console.error(`[astro-proxy] ERROR Response:`, text);
    }

    return new Response(text, {
      status: response.status,
      headers: {
        ...corsHeaders,
        "Content-Type": response.headers.get("content-type") || "application/json",
      },
    });
  } catch (e) {
    clearTimeout(timeoutId);
    const err = e as Error;
    if (err.name === "AbortError") {
      console.error(`[astro-proxy] Request timeout for ${path}`);
      return new Response(
        JSON.stringify({ detail: "Tempo limite excedido. Tente novamente." }),
        { status: 504, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }
    throw e;
  }
}

/**
 * Normalize payload for /v1/time/resolve-tz
 * Backend expects: year, month, day, hour, minute, second (NO natal_ prefix)
 */
function normalizeResolveTzPayload(body: Record<string, unknown>): Record<string, unknown> {
  if ("natal_year" in body) {
    return {
      year: body.natal_year,
      month: body.natal_month,
      day: body.natal_day,
      hour: body.natal_hour,
      minute: body.natal_minute,
      second: body.natal_second ?? 0,
      lat: body.lat,
      lng: body.lng,
      timezone: body.timezone,
    };
  }
  return body;
}

/**
 * Normalize payload for /v1/chart/natal and /v1/chart/transits
 * Backend expects: natal_year, natal_month, natal_day, natal_hour, natal_minute, natal_second
 */
function normalizeNatalPayload(body: Record<string, unknown>): Record<string, unknown> {
  if ("year" in body && !("natal_year" in body)) {
    return {
      natal_year: body.year,
      natal_month: body.month,
      natal_day: body.day,
      natal_hour: body.hour,
      natal_minute: body.minute,
      natal_second: body.second ?? 0,
      lat: body.lat,
      lng: body.lng,
      timezone: body.timezone,
      tz_offset_minutes: body.tz_offset_minutes,
    };
  }
  return body;
}

/**
 * Normalize payload for /v1/chart/render-data
 * Backend expects: year, month, day, hour, minute, second (NO natal_ prefix)
 */
function normalizeRenderDataPayload(body: Record<string, unknown>): Record<string, unknown> {
  if ("natal_year" in body) {
    return {
      year: body.natal_year,
      month: body.natal_month,
      day: body.natal_day,
      hour: body.natal_hour,
      minute: body.natal_minute,
      second: body.natal_second ?? 0,
      lat: body.lat,
      lng: body.lng,
      timezone: body.timezone,
      tz_offset_minutes: body.tz_offset_minutes,
    };
  }
  return body;
}

/**
 * Normalize payload for /v1/chart/transits
 * Backend expects: natal_year, natal_month, etc. + target_date
 */
function normalizeTransitsPayload(body: Record<string, unknown>): Record<string, unknown> {
  const normalized = normalizeNatalPayload(body);
  if (!normalized.target_date) {
    normalized.target_date = new Date().toISOString().split("T")[0];
  }
  return normalized;
}

/**
 * Normalize payload for /v1/synastry/compare
 * Backend expects: person1 { natal_* }, person2 { natal_* }
 */
function normalizeSynastryPayload(body: Record<string, unknown>): Record<string, unknown> {
  const normalizePerson = (person: Record<string, unknown>) => {
    // If already has natal_ prefix, return as-is
    if ("natal_year" in person) return person;

    // Convert from year/month/day format
    if ("year" in person) {
      return {
        natal_year: person.year,
        natal_month: person.month,
        natal_day: person.day,
        natal_hour: person.hour ?? 12,
        natal_minute: person.minute ?? 0,
        natal_second: person.second ?? 0,
        lat: person.lat ?? -23.55,
        lng: person.lng ?? -46.63,
        timezone: person.timezone ?? "America/Sao_Paulo",
        tz_offset_minutes: person.tz_offset_minutes,
      };
    }

    // Convert from birthDate format
    if ("birthDate" in person) {
      const [year, month, day] = (person.birthDate as string).split("-").map(Number);
      const [hour, minute] = (person.birthTime as string || "12:00").split(":").map(Number);
      return {
        natal_year: year,
        natal_month: month,
        natal_day: day,
        natal_hour: hour,
        natal_minute: minute,
        natal_second: 0,
        lat: person.lat ?? -23.55,
        lng: person.lng ?? -46.63,
        timezone: person.timezone ?? "America/Sao_Paulo",
        tz_offset_minutes: person.tz_offset_minutes,
      };
    }

    return person;
  };

  const personA = normalizePerson((body.person_a || body.personA || body.person1) as Record<string, unknown>);
  const personB = normalizePerson((body.person_b || body.personB || body.person2) as Record<string, unknown>);
  return {
    person_a: personA,
    person_b: personB,
    // backward compatibility
    person1: personA,
    person2: personB,
  };
}

function normalizePersonChart(person: Record<string, unknown> | undefined): Record<string, unknown> | undefined {
  if (!person) return undefined;
  if ("natal_year" in person) return person;

  if ("year" in person) {
    return {
      natal_year: person.year,
      natal_month: person.month,
      natal_day: person.day,
      natal_hour: person.hour ?? 12,
      natal_minute: person.minute ?? 0,
      natal_second: person.second ?? 0,
      lat: person.lat ?? -23.55,
      lng: person.lng ?? -46.63,
      timezone: person.timezone ?? "America/Sao_Paulo",
      tz_offset_minutes: person.tz_offset_minutes,
    };
  }

  if ("birthDate" in person) {
    const [year, month, day] = (person.birthDate as string).split("-").map(Number);
    const [hour, minute] = (person.birthTime as string || "12:00").split(":").map(Number);
    return {
      natal_year: year,
      natal_month: month,
      natal_day: day,
      natal_hour: hour,
      natal_minute: minute,
      natal_second: 0,
      lat: person.lat ?? -23.55,
      lng: person.lng ?? -46.63,
      timezone: person.timezone ?? "America/Sao_Paulo",
      tz_offset_minutes: person.tz_offset_minutes,
    };
  }

  return person;
}

function normalizeCosmicDecisionPayload(body: Record<string, unknown>): Record<string, unknown> {
  const normalized = normalizeNatalPayload(body);
  const optionalPerson = normalizePersonChart(
    body.optional_person_chart as Record<string, unknown> | undefined
  );
  return {
    ...normalized,
    question: body.question,
    question_type: body.question_type,
    optional_person_chart: optionalPerson,
  };
}

/**
 * Normalize payload for /v1/ai/cosmic-chat
 * Backend expects: message, history (optional), context (optional)
 */
function normalizeChatPayload(body: Record<string, unknown>): Record<string, unknown> {
  return {
    message: body.message,
    history: body.history || [],
    context: body.context || {},
  };
}

/**
 * Normalize Solar Return payload
 * Backend expects: natal_*, return_year, location (optional)
 */
function normalizeSolarReturnPayload(body: Record<string, unknown>): Record<string, unknown> {
  if (body.natal && body.alvo) return body;

  const normalized = normalizeNatalPayload(body);
  const year = Number(body.year ?? body.return_year ?? new Date().getFullYear());
  const timezone = String(normalized.timezone ?? "America/Sao_Paulo");
  const birthDate = `${normalized.natal_year}-${pad2(Number(normalized.natal_month))}-${pad2(Number(normalized.natal_day))}`;
  const birthTime = `${pad2(Number(normalized.natal_hour ?? 12))}:${pad2(Number(normalized.natal_minute ?? 0))}:00`;
  const lat = Number(normalized.lat ?? -23.5505);
  const lon = Number(normalized.lng ?? -46.6333);

  return {
    natal: {
      data: birthDate,
      hora: birthTime,
      timezone,
      local: { lat, lon },
    },
    alvo: {
      ano: year,
      local: { lat, lon },
      timezone,
    },
  };
}

function normalizeSolarReturnTimelinePayload(body: Record<string, unknown>): Record<string, unknown> {
  if (body.natal && (body.year || body.ano)) return body;

  const normalized = normalizeNatalPayload(body);
  const year = Number(body.year ?? body.ano ?? new Date().getFullYear());
  const timezone = String(normalized.timezone ?? "America/Sao_Paulo");
  const birthDate = `${normalized.natal_year}-${pad2(Number(normalized.natal_month))}-${pad2(Number(normalized.natal_day))}`;
  const birthTime = `${pad2(Number(normalized.natal_hour ?? 12))}:${pad2(Number(normalized.natal_minute ?? 0))}:00`;
  const lat = Number(normalized.lat ?? -23.5505);
  const lon = Number(normalized.lng ?? -46.6333);

  return {
    natal: {
      data: birthDate,
      hora: birthTime,
      timezone,
      local: { lat, lon },
    },
    year,
  };
}

/**
 * Normalize Progressions payload
 * Backend expects: natal_*, target_date
 */
function normalizeProgressionsPayload(body: Record<string, unknown>): Record<string, unknown> {
  const normalized = normalizeNatalPayload(body);
  if (!normalized.target_date) {
    normalized.target_date = toTodayIso();
  }
  return normalized;
}

/**
 * Normalize Lunations payload
 * Backend expects: date, timezone|tz_offset_minutes
 */
function normalizeLunationsPayload(body: Record<string, unknown>): Record<string, unknown> {
  if (body.date || body.targetDate) {
    return {
      date: body.date ?? body.targetDate,
      timezone: body.timezone ?? "America/Sao_Paulo",
      tz_offset_minutes: body.tz_offset_minutes,
      strict_timezone: body.strict_timezone ?? false,
    };
  }

  const normalized = normalizeNatalPayload(body);
  const date = normalized.target_date
    ? String(normalized.target_date)
    : `${normalized.natal_year}-${pad2(Number(normalized.natal_month))}-${pad2(Number(normalized.natal_day))}`;

  return {
    date,
    timezone: normalized.timezone ?? "America/Sao_Paulo",
    tz_offset_minutes: normalized.tz_offset_minutes,
    strict_timezone: false,
  };
}

function normalizeInsightsPayload(body: Record<string, unknown>): Record<string, unknown> {
  const normalized = normalizeNatalPayload(body);
  if (!normalized.target_date) {
    normalized.target_date = toTodayIso();
  }
  return normalized;
}

/**
 * Resolve timezone offset if missing but timezone is provided
 */
async function ensureTzOffset(
  baseUrl: string,
  apiKey: string,
  userId: string,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  if (body.tz_offset_minutes !== undefined) {
    return body;
  }

  if (!body.timezone) {
    return body;
  }

  const year = body.natal_year ?? body.year ?? 2000;
  const month = body.natal_month ?? body.month ?? 1;
  const day = body.natal_day ?? body.day ?? 1;
  const cacheKey = `${body.timezone}:${year}-${month}-${day}`;

  if (tzCache.has(cacheKey)) {
    devLog(`TZ cache hit: ${cacheKey}`);
    return { ...body, tz_offset_minutes: tzCache.get(cacheKey) };
  }

  try {
    devLog(`Resolving timezone: ${cacheKey}`);
    const tzPayload = normalizeResolveTzPayload(body);

    const response = await fetch(`${baseUrl.replace(/\/+$/, "")}/v1/time/resolve-tz`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${apiKey}`,
        "X-User-Id": userId,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(tzPayload),
    });

    if (response.ok) {
      const data = await response.json();
      if (data.tz_offset_minutes !== undefined) {
        tzCache.set(cacheKey, data.tz_offset_minutes);
        devLog(`TZ resolved: ${data.tz_offset_minutes} minutes`);
        return { ...body, tz_offset_minutes: data.tz_offset_minutes };
      }
    }
  } catch (e) {
    console.warn("[astro-proxy] Failed to resolve timezone:", e);
  }

  return body;
}

/**
 * Validate allowed paths
 */
function isPathAllowed(path: string): boolean {
  const allowedPrefixes = [
    "/v1/account/",
    "/v1/astro/",
    "/v1/chart/",
    "/v1/checkin/",
    "/v1/cycles/",
    "/v1/interpretation/",
    "/v1/daily/",
    "/v1/transits/",
    "/v1/alerts/",
    "/v1/notifications/",
    "/v1/cosmic-weather",
    "/v1/cosmic-timeline/",
    "/v1/moon/",
    "/v1/revolution-solar/",
    "/v1/solar-return/",
    "/v1/synastry/",
    "/v1/forecast/",
    "/v1/ai/",
    "/v1/insights/",
    "/v1/cosmic/",
    "/v1/progressions/",
    "/v1/lunations/",
    "/v1/time/",
    "/v1/system/",
    "/chart",
    "/interpretation",
    "/api/",
    "/health",
  ];

  return allowedPrefixes.some(prefix => path.startsWith(prefix)) || path === "/";
}

serve(async (req) => {
  // CORS preflight
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    // Validate authentication
    const { userId, error: authError } = await validateAuth(req);
    if (authError) {
      return authError;
    }

    const ASTRO_API_BASE_URL = Deno.env.get("ASTRO_API_BASE_URL");
    const ASTRO_API_KEY = Deno.env.get("API_KEY");
    const requestId = crypto.randomUUID();

    if (!ASTRO_API_BASE_URL || !ASTRO_API_KEY) {
      console.error("[astro-proxy] Secrets not configured");
      return new Response(
        JSON.stringify({ detail: "Secrets não configurados: ASTRO_API_BASE_URL/API_KEY" }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }
    const baseUrl = sanitizeBaseUrl(ASTRO_API_BASE_URL);
    devLog("request_in", { request_id: requestId, method: req.method, url: req.url, base_url: baseUrl });

    // Parse request payload
    let payload: Record<string, unknown> = {};
    try {
      payload = await req.json();
    } catch {
      payload = {};
    }

    const path = (payload.path as string) || "/";
    const method = ((payload.method as string) || "GET").toUpperCase();
    let body = payload.body as Record<string, unknown> | undefined;
    let normalizationApplied = false;

    // Security: validate path
    if (!isPathAllowed(path)) {
      console.warn(`[astro-proxy] Blocked path: ${path}`);
      return new Response(
        JSON.stringify({ detail: "Path não permitido" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Normalize payloads based on endpoint
    if (body) {
      if (path === "/v1/time/resolve-tz") {
        normalizationApplied = true;
        body = normalizeResolveTzPayload(body);
        devLog("Normalized resolve-tz payload", body);
      } else if (path === "/v1/chart/natal") {
        normalizationApplied = true;
        body = normalizeNatalPayload(body);
        body = await ensureTzOffset(baseUrl, ASTRO_API_KEY, userId, body);
        devLog("Normalized natal payload", body);
      } else if (path === "/v1/chart/render-data") {
        normalizationApplied = true;
        body = normalizeRenderDataPayload(body);
        body = await ensureTzOffset(baseUrl, ASTRO_API_KEY, userId, body);
        devLog("Normalized render-data payload", body);
      } else if (path === "/v1/chart/distributions") {
        normalizationApplied = true;
        body = normalizeNatalPayload(body);
        body = await ensureTzOffset(baseUrl, ASTRO_API_KEY, userId, body);
        devLog("Normalized distributions payload", body);
      } else if (path === "/v1/chart/transits" || path.startsWith("/v1/transits/")) {
        normalizationApplied = true;
        body = normalizeTransitsPayload(body);
        body = await ensureTzOffset(baseUrl, ASTRO_API_KEY, userId, body);
        devLog("Normalized transits payload", body);
      } else if (path.startsWith("/v1/synastry/")) {
        normalizationApplied = true;
        body = normalizeSynastryPayload(body);
        devLog("Normalized synastry payload", body);
      } else if (path === "/v1/forecast/personal") {
        normalizationApplied = true;
        body = normalizeNatalPayload(body);
        body = await ensureTzOffset(baseUrl, ASTRO_API_KEY, userId, body);
        devLog("Normalized forecast payload", body);
      } else if (path === "/v1/ai/cosmic-chat") {
        normalizationApplied = true;
        body = normalizeChatPayload(body);
        devLog("Normalized chat payload", body);
      } else if (path === "/api/chat/astral-oracle") {
        normalizationApplied = true;
        // Map message to question for backend compatibility as per integration-report
        body = {
          ...body,
          question: body.message,
          userId: userId
        };
        devLog("Normalized astral-oracle payload", body);
      } else if (path === "/v1/solar-return/timeline") {
        normalizationApplied = true;
        body = normalizeSolarReturnTimelinePayload(body);
        devLog("Normalized solar-return timeline payload", body);
      } else if (path.startsWith("/v1/solar-return/") || path.startsWith("/v1/revolution-solar/")) {
        normalizationApplied = true;
        body = normalizeSolarReturnPayload(body);
        body = await ensureTzOffset(baseUrl, ASTRO_API_KEY, userId, body);
        devLog("Normalized solar-return payload", body);
      } else if (path.startsWith("/v1/cycles/")) {
        normalizationApplied = true;
        body = normalizeNatalPayload(body);
        body = await ensureTzOffset(baseUrl, ASTRO_API_KEY, userId, body);
        devLog("Normalized cycles payload", body);
      } else if (path.startsWith("/v1/progressions/")) {
        normalizationApplied = true;
        body = normalizeProgressionsPayload(body);
        body = await ensureTzOffset(baseUrl, ASTRO_API_KEY, userId, body);
        devLog("Normalized progressions payload", body);
      } else if (path.startsWith("/v1/lunations/")) {
        normalizationApplied = true;
        body = normalizeLunationsPayload(body);
        devLog("Normalized lunations payload", body);
      } else if (path.startsWith("/v1/interpretation/") || path.startsWith("/v1/insights/")) {
        normalizationApplied = true;
        body = normalizeInsightsPayload(body);
        body = await ensureTzOffset(baseUrl, ASTRO_API_KEY, userId, body);
        devLog("Normalized interpretation payload", body);
      } else if (path.startsWith("/v1/cosmic/")) {
        normalizationApplied = true;
        body = normalizeCosmicDecisionPayload(body);
        body = await ensureTzOffset(baseUrl, ASTRO_API_KEY, userId, body);
        devLog("Normalized cosmic payload", body);
      }
    }

    return await proxyFetch(baseUrl, ASTRO_API_KEY, path, method, body, userId, requestId, normalizationApplied);

  } catch (e) {
    console.error("[astro-proxy] Error:", e);
    return new Response(
      JSON.stringify({ detail: "Erro no astro-proxy", error: String(e) }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});


