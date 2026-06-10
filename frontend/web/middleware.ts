/**
 * v2.2：路由保护
 *
 * 策略：
 *   - /admin/*         → 需要 admin 角色（cookie: mediaradar_role=admin）
 *   - /(app)/*         → 需要任意已登录用户（cookie: mediaradar_token_cookie 存在）
 *   - 其他（/login, /auth/callback, /api, /_next, 静态资源）→ 放行
 *
 * 注：v2 暂不上 NextAuth 5（localStorage 流程 + 角色 cookie 兜底）。
 *   v3 若切 server-side session 再评估 NextAuth 集成。
 */
import { NextResponse, type NextRequest } from 'next/server';

const TOKEN_COOKIE = 'mediaradar_token_cookie';
const ROLE_COOKIE = 'mediaradar_role';

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // /admin/* 严格保护
  if (pathname.startsWith('/admin')) {
    const role = request.cookies.get(ROLE_COOKIE)?.value;
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
    const token = request.cookies.get(TOKEN_COOKIE)?.value;
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
