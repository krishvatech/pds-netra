import { NextRequest, NextResponse } from 'next/server';

const SESSION_COOKIE = 'pdsnetra_session';
const USER_COOKIE = 'pdsnetra_user';
const SESSION_MAX_AGE_SEC = 60 * 60 * 12;
const MAX_PROXY_HOPS = 2;

export const dynamic = 'force-dynamic';

type RouteCtx = { params: Promise<{ path?: string[] }> };

function sanitizeUserCookiePayload(raw: any): any | null {
  if (!raw || typeof raw !== 'object') return null;
  const role = typeof raw.role === 'string' ? raw.role : undefined;
  const username = typeof raw.username === 'string' ? raw.username : undefined;
  if (!role || !username) return null;
  return {
    id: typeof raw.id === 'string' ? raw.id : undefined,
    username,
    name: typeof raw.name === 'string' ? raw.name : undefined,
    role,
    district: typeof raw.district === 'string' || raw.district === null ? raw.district : null,
    godown_id: typeof raw.godown_id === 'string' || raw.godown_id === null ? raw.godown_id : null
  };
}

function backendBaseUrl(req: NextRequest): string {
  const internal = (process.env.BACKEND_INTERNAL_API_BASE_URL || '').trim();
  if (internal) return internal.replace(/\/+$/, '');

  // Safe default inside docker-compose network. This avoids accidental
  // public-domain self loops when proxy headers/host differ across hops.
  const dockerInternal = 'http://backend:8001';

  const configured = (process.env.NEXT_PUBLIC_API_BASE_URL || '').trim();
  if (!configured) return dockerInternal;

  // Avoid proxy self-loop when public base points to this same origin.
  try {
    const upstream = new URL(configured);
    const current = req.nextUrl;
    if (upstream.hostname === 'backend' || upstream.hostname === '127.0.0.1' || upstream.hostname === 'localhost') {
      return configured.replace(/\/+$/, '');
    }
    if (upstream.host === current.host) {
      return dockerInternal;
    }
  } catch {
    // Non-absolute values are risky here; keep internal route.
    return dockerInternal;
  }
  // Do not use arbitrary public origins from server-side proxy.
  return dockerInternal;
}

function decodeUserCookie(raw: string | undefined): any | null {
  if (!raw) return null;
  try {
    return sanitizeUserCookiePayload(JSON.parse(decodeURIComponent(raw)));
  } catch {
    return null;
  }
}

function buildForwardHeaders(req: NextRequest): Headers {
  const headers = new Headers();
  req.headers.forEach((value, key) => {
    const k = key.toLowerCase();
    if (
      k === 'host' ||
      k === 'connection' ||
      k === 'content-length' ||
      k === 'cookie' ||
      k === 'if-none-match' ||
      k === 'if-modified-since' ||
      k === 'forwarded' ||
      k === 'via' ||
      k === 'x-real-ip' ||
      k === 'x-forwarded-for' ||
      k === 'x-forwarded-host' ||
      k === 'x-forwarded-proto' ||
      k === 'x-forwarded-port' ||
      k.startsWith('cf-')
    ) return;
    headers.set(key, value);
  });

  const inboundHopRaw = req.headers.get('x-pds-proxy-hop');
  const inboundHop = inboundHopRaw ? Number.parseInt(inboundHopRaw, 10) : 0;
  const nextHop = Number.isFinite(inboundHop) ? inboundHop + 1 : 1;
  headers.set('X-PDS-Proxy-Hop', String(nextHop));

  const token = req.cookies.get(SESSION_COOKIE)?.value;
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const user = decodeUserCookie(req.cookies.get(USER_COOKIE)?.value);
  if (user?.role) headers.set('X-User-Role', String(user.role));
  if (user?.godown_id) headers.set('X-User-Godown', String(user.godown_id));
  if (user?.district) headers.set('X-User-District', String(user.district));
  if (user?.name) headers.set('X-User-Name', String(user.name));
  return headers;
}

function applySessionCookies(resp: NextResponse, token: string, user: any): void {
  const secure = process.env.NODE_ENV === 'production';
  const compactUser = sanitizeUserCookiePayload(user) ?? {};
  resp.cookies.set({
    name: SESSION_COOKIE,
    value: token,
    httpOnly: true,
    secure,
    sameSite: 'lax',
    path: '/',
    maxAge: SESSION_MAX_AGE_SEC
  });
  resp.cookies.set({
    name: USER_COOKIE,
    value: encodeURIComponent(JSON.stringify(compactUser)),
    httpOnly: false,
    secure,
    sameSite: 'lax',
    path: '/',
    maxAge: SESSION_MAX_AGE_SEC
  });
}

function clearSessionCookies(resp: NextResponse): void {
  const secure = process.env.NODE_ENV === 'production';
  resp.cookies.set({ name: SESSION_COOKIE, value: '', httpOnly: true, secure, sameSite: 'lax', path: '/', maxAge: 0 });
  resp.cookies.set({ name: USER_COOKIE, value: '', httpOnly: false, secure, sameSite: 'lax', path: '/', maxAge: 0 });
}

async function handle(req: NextRequest, ctx: RouteCtx): Promise<NextResponse> {
  const { path = [] } = await ctx.params;
  const joined = path.join('/');
  const method = req.method.toUpperCase();
  const inboundHopRaw = req.headers.get('x-pds-proxy-hop');
  const inboundHop = inboundHopRaw ? Number.parseInt(inboundHopRaw, 10) : 0;
  if (Number.isFinite(inboundHop) && inboundHop > MAX_PROXY_HOPS) {
    return NextResponse.json({ detail: 'Proxy loop detected' }, { status: 508 });
  }

  if (joined === 'auth/session' && method === 'GET') {
    const token = req.cookies.get(SESSION_COOKIE)?.value;
    const user = decodeUserCookie(req.cookies.get(USER_COOKIE)?.value);
    if (!token) return NextResponse.json({ detail: 'Unauthorized' }, { status: 401 });
    return NextResponse.json({ user: user || null }, { status: 200 });
  }

  if (joined === 'auth/logout' && method === 'POST') {
    const resp = NextResponse.json({ status: 'ok' }, { status: 200 });
    clearSessionCookies(resp);
    return resp;
  }

  const upstreamUrl = `${backendBaseUrl(req)}/api/v1/${joined}${req.nextUrl.search}`;
  const headers = buildForwardHeaders(req);
  if (joined === 'auth/login' || joined === 'auth/register') {
    headers.delete('Authorization');
  }
  const body = method === 'GET' || method === 'HEAD' ? undefined : await req.arrayBuffer();

  const upstream = await fetch(upstreamUrl, {
    method,
    headers,
    body,
    redirect: 'manual',
    cache: 'no-store'
  });

  const isAuthBootstrap = (joined === 'auth/login' || joined === 'auth/register') && upstream.ok;
  if (isAuthBootstrap) {
    const payload = await upstream.json().catch(() => null);
    const token = payload?.access_token;
    const user = payload?.user || null;
    if (typeof token === 'string' && token) {
      const resp = NextResponse.json({ token_type: payload?.token_type || 'bearer', user }, { status: upstream.status });
      applySessionCookies(resp, token, user);
      return resp;
    }
  }

  const contentType = upstream.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');
  if (isJson) {
    const json = await upstream.json().catch(() => ({}));
    return NextResponse.json(json, { status: upstream.status });
  }

  const raw = await upstream.arrayBuffer();
  const resp = new NextResponse(raw, { status: upstream.status });
  const passHeaders = [
    'content-type',
    'cache-control',
    'content-disposition',
    'x-frame-captured-at',
    'x-frame-age-seconds',
    'x-frame-stale',
    'x-frame-stale-threshold-seconds'
  ];
  for (const key of passHeaders) {
    const v = upstream.headers.get(key);
    if (v) resp.headers.set(key, v);
  }
  return resp;
}

export async function GET(req: NextRequest, ctx: RouteCtx) {
  return handle(req, ctx);
}

export async function POST(req: NextRequest, ctx: RouteCtx) {
  return handle(req, ctx);
}

export async function PUT(req: NextRequest, ctx: RouteCtx) {
  return handle(req, ctx);
}

export async function PATCH(req: NextRequest, ctx: RouteCtx) {
  return handle(req, ctx);
}

export async function DELETE(req: NextRequest, ctx: RouteCtx) {
  return handle(req, ctx);
}
