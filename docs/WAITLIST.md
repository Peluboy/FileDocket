# Pro waitlist

Coming soon is inside the Go Pro modal. One email when checkout opens.

You do not need a Loops sending domain to **collect** waitlist emails. Those go to FormSubmit (your Gmail) until you paste a Loops form ID.

You **do** need a domain you control to **send** from Loops (the "Pro is live" campaign, and Loops double-opt-in mail). `github.io` cannot be that domain. Skip Loops sending until you buy a domain such as `mail.yourname.com`. Company address (Illinois, Chicago) is unrelated and fine.

## Loops form

1. Open [app.loops.so](https://app.loops.so) and sign in with the same Google account as GA4.
2. **Audience → Lists → New list.** Name it `Pro waitlist`. Make it **Public**.
3. **Forms.** Open **Settings** and copy **Form Endpoint**. It looks like:
   `https://app.loops.so/api/newsletter-form/YOUR_FORM_ID`
4. Paste `YOUR_FORM_ID` into `LOOPS_FORM_ID` in `docs/index.html`.
5. In the same form settings, turn on **double opt-in**.
6. Test Go Pro on the landing page. The contact should appear under Audience, in `Pro waitlist`.

When Lemon Squeezy is live:

1. Swap Coming soon back to Get Pro with the live checkout URL.
2. In Loops, send **one** campaign to `Pro waitlist`. Link the checkout page. That is the whole announcement.

## Buttondown

1. Create a newsletter at [buttondown.com](https://buttondown.com).
2. Your public username is in the URL (`buttondown.com/USERNAME`).
3. Paste `USERNAME` into `BUTTONDOWN_USER` in `docs/index.html`. Leave `LOOPS_FORM_ID` empty.

## Kit (ConvertKit)

1. Create a form at [kit.com](https://kit.com) (Forms → New form).
2. Copy the numeric form ID from the form’s embed or share URL.
3. Paste it into `KIT_FORM_ID` in `docs/index.html`. Leave the other two IDs empty.

## FormSubmit (default until an ID is set)

The first submit sends an activation mail to `imulep2104@gmail.com`. Confirm that once. After that, waitlist rows arrive as email. This is a holding inbox, not a broadcast list. Move to Loops before you announce Pro.

## Priority

If more than one ID is filled, the page uses Loops, then Buttondown, then Kit, then FormSubmit.
