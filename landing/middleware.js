export default function middleware(request) {
  const url = new URL(request.url);

  // Only handle /install.sh
  if (url.pathname !== '/install.sh') {
    return;
  }

  // Check if it's a browser (accepts HTML) vs curl/wget (doesn't)
  const acceptHeader = request.headers.get('accept') || '';
  const isBrowser = acceptHeader.includes('text/html');

  if (isBrowser) {
    // Redirect browsers to a friendly page
    return Response.redirect(new URL('/install-help.html', request.url), 302);
  }

  // For curl/wget, let it pass through to the actual script
  return;
}

export const config = {
  matcher: '/install.sh',
};
