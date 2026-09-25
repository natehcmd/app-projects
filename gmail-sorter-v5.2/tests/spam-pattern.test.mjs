// node tests/spam-pattern.test.mjs — exits 1 on any failure.
import { isSpamPattern } from '../src/preferences-io.mjs';

const P = (domains) => ({ spamPatterns: { domains, emails: [], subjectPatterns: [], bodyPatterns: [] } });
const cases = [
  ['user@gmail.com', ['mail.com'], false, 'a blocked domain no longer matches as a substring'],
  ['Spam <x@mail.com>', ['mail.com'], true, 'exact domain inside <...>'],
  ['x@news.mail.com', ['mail.com'], true, 'subdomain of a blocked domain'],
  ['plain@spam.io', ['spam.io'], true, 'bare address without <...> is still checked'],
  ["'alice@x.com' via Group <group@googlegroups.com>", ['x.com'], false, 'an @ in the display name is ignored'],
  ["'alice@x.com' via Group <group@googlegroups.com>", ['googlegroups.com'], true, 'the real sender domain is used'],
  ['No Address', ['mail.com'], false, 'no address is not spam'],
];
let failed = 0;
for (const [from, domains, want, name] of cases) {
  const got = isSpamPattern(from, '', '', P(domains));
  console.log(got === want ? 'ok  ' : 'FAIL', name);
  if (got !== want) failed++;
}
process.exit(failed ? 1 : 0);
