/**
 * v2.2：路由保护
 *
 * 策略：
 *   - /admin/*         → 需要 admin 角色（从 JWT payload 中解析，不再信任 mediaradar_role cookie）
 *   - /(app)/*         → 需要任意已登录用户（cookie: mediaradar_token_cookie 存在）
 *   - 其他（/login, /auth/callback, /api, /_next, 静态资源）→ 放行
 *
 * 安全说明：
 *   middleware 仅做 UX 层重定向，最终授权依然由后端 require_admin 把关。
 *   JWT 在 Edge runtime 内不做密钥校验（无 jose 依赖），但伪造的 token
 *   会在第一次 API 调用时被后端拒绝（gateway 用 JWT_SECRET 校验）。
 */
import { NextResponse, type NextRequest } from 'next/server';

const TOKEN_COOKIE = 'mediaradar_token_cookie';

function _b64UrlDecode(input: string): string {
  // edge-runtime atob 不支持 url-safe base64，需先转回标准 base64
  const padded = input + '='.repeat((4 - (input.length % 4)) % 4);
  const std = padded.replace(/-/g, '+').replace(/_/g, '/');
  try {
    return atob(std);
  } catch {
    return '';
  }
}

function _decodeRoleFromJwt(token: string): string | null {
  // JWT 三段式 header.payload.sig，仅取 payload；不做签名校验
  const parts = token.split('.');
  if (parts.length !== 3) return null;
  try {
    const payload = JSON.parse(_b64UrlDecode(parts[1]) || '{}');
    const role = typeof payload.role === 'string' ? payload.role : null;
    const exp = typeof payload.exp === 'number' ? payload.exp : null;
    if (exp && Date.now() / 1000 >= exp) {
      return null;  // 已过期
    }
    return role;
  } catch {
    return null;
  }
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const token = request.cookies.get(TOKEN_COOKIE)?.value || '';
  const role = token ? _decodeRoleFromJwt(token) : null;

  // /admin/* 严格保护
  if (pathname.startsWith('/admin')) {
    if (role !== 'admin') {
      const loginUrl = new URL('/login', request.url);
      loginUrl.searchParams.set('redirect', pathname);
      return NextResponse.redirect(loginUrl);
    }
    return NextResponse.next();
  }

  // /(app)/* 普通登录保护
  // (app) 在 Next.js 15 是路由组，不出现在 URL 中，所以这里保护所有非公开路径
  if (
    pathname.startsWith('/dashboard') ||
    pathname.startsWith('/agent') ||
    pathname.startsWith('/yq-list') ||
    pathname.startsWith('/settings')
  ) {
    if (!token) {
      const loginUrl = new URL('/login', request.url);
      loginUrl.searchParams.set('redirect', pathname);
      return NextResponse.redirect(loginUrl);
    }
    return NextResponse.next();
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * 匹配所有路径除了：
     * - api (API routes)
     * - _next/static (静态文件)
     * - _next/image (图片优化)
     * - favicon.ico, robots.txt 等静态资源
     * - 登录/回调页（自身就在登录流程中）
     */
    '/((?!api|_next/static|_next/image|favicon.ico|robots.txt|login|auth/callback).*)',
  ],
};
