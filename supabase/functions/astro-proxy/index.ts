import { serve } from "https://deno.land/std@0.224.0/http/server.ts";

type JsonRecord = Record<string, unknown>;

type RenderDataNormalizationConfig = {
  natalPrefix?: string;
};

type SynastryPersonPayload = {
  birth_date?: string;
  birth_time?: string | null;
  natal_year?: number;
  natal_month?: number;
  natal_day?: number;
  natal_hour?: number;
  natal_minute?: number;
  natal_second?: number;
  timezone?: string | null;
  tz_offset_minutes?: number | null;
  lat?: number;
  lng?: number;
  name?: string | null;
  [key: string]: unknown;
};

type ProxyEnvelope = {
  method?: string;
  path?: string;
  body?: JsonRecord;
  query?: Record<string, string | number | boolean | null | undefined>;
  [key: string]: unknown;
};

const RENDER_DATA_DATE_FIELDS = [
  "year",
  "month",
  "day",
  "hour",
  "minute",
  "second",
] as const;

const DEFAULT_CONFIG: RenderDataNormalizationConfig = {
  natalPrefix: "natal_",
};

const ALLOWED_EXACT_PATHS = new Set([
  "/",
  "/health",
  "/api-test",
  "/api/chat/astral-oracle",
  "/api/lunar-calendar",
  "/api/secondary-progressions",
  "/api/solar-return",
  "/v1/account/status",
  "/v1/account/plan",
  "/v1/account/plan-status",
  "/v1/ai/cosmic-chat",
  "/v1/alerts/retrogrades",
  "/v1/alerts/system",
  "/v1/astro/chart",
  "/v1/astro/chart/render-spec",
  "/v1/astro/composite",
  "/v1/astro/lunar-phases",
  "/v1/astro/progressions",
  "/v1/astro/solar-return",
  "/v1/astro/synastry",
  "/v1/astro/transits",
  "/v1/billing/entitlements",
  "/v1/billing/status",
  "/v1/bugs/report",
  "/v1/chart/distributions",
  "/v1/chart/natal",
  "/v1/chart/render-data",
  "/v1/chart/transits",
  "/v1/cosmic-timeline/next-7-days",
  "/v1/cosmic-weather",
  "/v1/cosmic-weather/range",
  "/v1/daily/summary",
  "/v1/dev/login-as",
  "/v1/diagnostics/ephemeris-check",
  "/v1/i18n/ptbr",
  "/v1/i18n/validate",
  "/v1/insights/areas-activated",
  "/v1/insights/care-suggestion",
  "/v1/insights/dominant-theme",
  "/v1/insights/life-cycles",
  "/v1/insights/mercury-retrograde",
  "/v1/insights/solar-return",
  "/v1/interpretation/natal",
  "/v1/lunations/calculate",
  "/v1/moon/timeline",
  "/v1/notifications/daily",
  "/v1/oracle/chat",
  "/v1/progressions/secondary/calculate",
  "/v1/revolution-solar/current-year",
  "/v1/solar-return/calculate",
  "/v1/solar-return/overlay",
  "/v1/solar-return/timeline",
  "/v1/synastry/compare",
  "/v1/system/endpoints",
  "/v1/system/health",
  "/v1/system/roadmap",
  "/v1/telemetry/event",
  "/v1/time/resolve-tz",
  "/v1/time/validate-local-datetime",
  "/v1/transits/events",
  "/v1/transits/live",
  "/v1/transits/next-days",
  "/v1/transits/personal-today",
]);

const ALLOWED_DYNAMIC_PREFIXES = [
  "/api/daily-analysis/",
];

export const normalizeRenderDataPayload = (
  payload: JsonRecord,
  config: RenderDataNormalizationConfig = DEFAULT_CONFIG,
): JsonRecord => {
  const normalized: JsonRecord = { ...payload };
  const prefix = config.natalPrefix ?? "natal_";

  for (const field of RENDER_DATA_DATE_FIELDS) {
    const natalField = `${prefix}${field}`;
    const hasRenderField = normalized[field] !== undefined;
    const natalValue = payload[natalField];

    if (!hasRenderField && natalValue !== undefined) {
      normalized[field] = natalValue;
    }

    if (normalized[natalField] !== undefined) {
      delete normalized[natalField];
    }
  }

  return normalized;
};

const pad2 = (value: number) => String(value).padStart(2, "0");

const normalizeSynastryPerson = (
  person: SynastryPersonPayload,
): SynastryPersonPayload => {
  const normalized: SynastryPersonPayload = { ...person };

  if (!normalized.birth_date && normalized.natal_year !== undefined) {
    const year = normalized.natal_year;
    const month = normalized.natal_month;
    const day = normalized.natal_day;
    if (
      typeof year === "number" &&
      typeof month === "number" &&
      typeof day === "number"
    ) {
      normalized.birth_date = `${year}-${pad2(month)}-${pad2(day)}`;
    }
  }

  if (!normalized.birth_time && normalized.natal_hour !== undefined) {
    const hour = normalized.natal_hour;
    const minute = normalized.natal_minute ?? 0;
    const second = normalized.natal_second ?? 0;
    if (
      typeof hour === "number" &&
      typeof minute === "number" &&
      typeof second === "number"
    ) {
      normalized.birth_time = `${pad2(hour)}:${pad2(minute)}:${pad2(second)}`;
    }
  }

  return normalized;
};

const normalizeSynastryPayload = (payload: JsonRecord): JsonRecord => {
  const normalized: JsonRecord = { ...payload };
  const personA = (payload.person_a ?? payload.person1) as
    | SynastryPersonPayload
    | undefined;
  const personB = (payload.person_b ?? payload.person2) as
    | SynastryPersonPayload
    | undefined;

  if (personA && normalized.person_a === undefined) {
    normalized.person_a = normalizeSynastryPerson(personA);
  }

  if (personB && normalized.person_b === undefined) {
    normalized.person_b = normalizeSynastryPerson(personB);
  }

  return normalized;
};

const upstreamUrl = Deno.env.get("ASTRO_API_URL") ?? "http://localhost:8000";

const isAllowedPath = (path: string): boolean => {
  if (ALLOWED_EXACT_PATHS.has(path)) {
    return true;
  }
  return ALLOWED_DYNAMIC_PREFIXES.some((prefix) => path.startsWith(prefix));
};

const readJsonSafely = async (req: Request): Promise<JsonRecord | undefined> => {
  const contentType = req.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return undefined;
  }

  try {
    return (await req.json()) as JsonRecord;
  } catch {
    return undefined;
  }
};

serve(async (req) => {
  const url = new URL(req.url);
  const upstreamUrlObject = new URL(upstreamUrl);
  const queryParams = new URLSearchParams(url.search);
  const requestHeaders = new Headers(req.headers);
  requestHeaders.set("host", upstreamUrlObject.host);

  const incomingBody = await readJsonSafely(req);
  const envelope = (incomingBody ?? {}) as ProxyEnvelope;

  const rawPathFromEnvelope =
    typeof envelope.path === "string" && envelope.path.trim().startsWith("/")
      ? envelope.path.trim()
      : undefined;
  const rawMethodFromEnvelope =
    typeof envelope.method === "string" && envelope.method.trim().length > 0
      ? envelope.method.trim().toUpperCase()
      : undefined;

  const [envelopePathOnly, envelopeQueryString] = rawPathFromEnvelope
    ? rawPathFromEnvelope.split("?", 2)
    : [undefined, undefined];

  const upstreamPath =
    envelopePathOnly && envelopePathOnly !== "/"
      ? envelopePathOnly
      : url.pathname;

  if (!isAllowedPath(upstreamPath)) {
    return new Response(
      JSON.stringify({ detail: "Path não permitido", path: upstreamPath }),
      { status: 400, headers: { "content-type": "application/json" } },
    );
  }

  if (envelopeQueryString) {
    const parsed = new URLSearchParams(envelopeQueryString);
    for (const [k, v] of parsed.entries()) {
      if (!queryParams.has(k)) {
        queryParams.set(k, v);
      }
    }
  }

  if (envelope.query && typeof envelope.query === "object") {
    for (const [key, value] of Object.entries(envelope.query)) {
      if (value === null || value === undefined) continue;
      if (!queryParams.has(key)) {
        queryParams.set(key, String(value));
      }
    }
  }

  const targetMethod = rawMethodFromEnvelope ?? req.method.toUpperCase();

  let body: string | undefined;

  if (targetMethod !== "GET" && targetMethod !== "HEAD") {
    let payload = (incomingBody ?? {}) as JsonRecord;

    if (rawPathFromEnvelope && envelope.body && typeof envelope.body === "object") {
      payload = envelope.body;
    }

    let normalizedPayload = payload;
    if (upstreamPath === "/v1/chart/render-data") {
      normalizedPayload = normalizeRenderDataPayload(payload);
    } else if (upstreamPath === "/v1/synastry/compare") {
      normalizedPayload = normalizeSynastryPayload(payload);
    }

    body = JSON.stringify(normalizedPayload);
    requestHeaders.set("content-type", "application/json");
  }

  const upstreamResponse = await fetch(
    `${upstreamUrlObject.origin}${upstreamPath}${
      queryParams.toString() ? `?${queryParams.toString()}` : ""
    }`,
    {
      method: targetMethod,
      headers: requestHeaders,
      body,
    },
  );

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    headers: upstreamResponse.headers,
  });
});
