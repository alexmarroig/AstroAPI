import { serve } from "https://deno.land/std@0.224.0/http/server.ts";

type JsonRecord = Record<string, unknown>;

type RenderDataNormalizationConfig = {
  natalPrefix?: string;
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
  }

  return normalized;
};

const upstreamUrl = Deno.env.get("ASTRO_API_URL") ?? "http://localhost:8000";

serve(async (req) => {
  const url = new URL(req.url);
  const upstreamPath = url.pathname;
  const targetPath = upstreamPath === "/api-test" ? "/health" : upstreamPath;
  const upstreamUrlObject = new URL(upstreamUrl);
  const queryParams = new URLSearchParams(url.search);

  const requestHeaders = new Headers(req.headers);
  requestHeaders.set("host", upstreamUrlObject.host);

  let body: string | undefined;

  if (req.method !== "GET" && req.method !== "HEAD") {
    const payload = (await req.json()) as JsonRecord;
    const normalizedPayload =
      upstreamPath === "/v1/chart/render-data"
        ? normalizeRenderDataPayload(payload)
        : payload;
    body = JSON.stringify(normalizedPayload);
    requestHeaders.set("content-type", "application/json");
  } else {
    const contentType = req.headers.get("content-type") ?? "";
    const contentLength = req.headers.get("content-length");
    const hasBody =
      contentType.includes("application/json") ||
      (contentLength !== null && contentLength !== "0");

    if (hasBody) {
      const rawBody = await req.text();
      if (rawBody) {
        try {
          const payload = JSON.parse(rawBody) as JsonRecord;
          for (const [key, value] of Object.entries(payload)) {
            if (value === null || value === undefined) {
              continue;
            }
            if (!queryParams.has(key)) {
              queryParams.set(key, String(value));
            }
          }
        } catch {
          // Ignore invalid JSON body on GET requests.
        }
      }
    }
  }

  const upstreamResponse = await fetch(
    `${upstreamUrlObject.origin}${targetPath}${
      queryParams.toString() ? `?${queryParams.toString()}` : ""
    }`,
    {
      method: req.method,
      headers: requestHeaders,
      body,
    },
  );

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    headers: upstreamResponse.headers,
  });
});
