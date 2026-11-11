# Supporters

## Unreleased

- Donation, goal and sponsor amounts use the app's money field (CHF prefix, 2 decimals, no arrows).

## 1.1.0

- Gives the standard roles access when a club first switches it on (`role_defaults`, docs/roles.md in hubra-app/hubra): Mitglied Ansehen, Vorstand Ansehen, Aktuar/in Bearbeiten, Kassier/in Alles. Roles without access don't see it; their own data from it stays on their profile. Needs Hubra 0.2.5 or later.
- Dashboard widgets: **Spendenziele** (open goals with raised, target and share) and **Sponsoren** (active sponsors and what they give a year; needs `supporters.sponsors.read`).
- The sponsors moved into Finanzen, as a page tab of their own
  (`/app/finance/sponsors`). The Supporters page keeps the fundraising goals;
  the old address `/app/supporters/sponsors` opens the new one.
- Recording a donation works again on Hubra with the books moved into the
  Finances plugin. The income is written to the transactions table directly
  instead of through a finance service that core no longer has.

## 1.0.0

First version: sponsor packages, sponsors with logos and yearly invoices,
fundraising goals with recorded donations and member pledges, and a public
endpoint for the club website.
