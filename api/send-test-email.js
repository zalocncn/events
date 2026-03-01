/**
 * Test endpoint: sends a simple email using the Resend SDK.
 * GET /api/send-test-email — sends "Hello World" to the address in RESEND_TEST_TO or query param "to".
 *
 * Set RESEND_API_KEY in Vercel (or .env) to your real API key. Do NOT commit the key.
 * Example: RESEND_API_KEY=re_xxxxxxxxx  (replace re_xxxxxxxxx with your key from resend.com)
 */
import { Resend } from 'resend';

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

export async function GET(request) {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    return jsonResponse(
      { error: 'Set RESEND_API_KEY in your environment (e.g. Vercel). Replace re_xxxxxxxxx with your real API key from resend.com.' },
      503
    );
  }

  const url = new URL(request.url);
  const to = url.searchParams.get('to') || process.env.RESEND_TEST_TO || 'zalocn@gmail.com';

  const resend = new Resend(apiKey);

  try {
    const { data, error } = await resend.emails.send({
      from: 'onboarding@resend.dev',
      to,
      subject: 'Hello World',
      html: '<p>Congrats on sending your <strong>first email</strong>!</p>',
    });

    if (error) {
      return jsonResponse({ error: error.message }, 400);
    }
    return jsonResponse({ ok: true, id: data?.id, to });
  } catch (e) {
    console.error('Resend send error:', e);
    return jsonResponse({ error: String(e.message || e) }, 500);
  }
}
