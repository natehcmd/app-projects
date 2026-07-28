# Classification Rules - Detailed Reference

**Complete breakdown of how emails are classified into 4 categories**

---

## The 4 Categories

### 1️⃣ IMPORTANT — Real Human Communication

**Definition:** Email from an actual person that requires your attention or response

**Characteristics:**
- ✓ Written by a human (conversational tone)
- ✓ Mentions specific projects, meetings, or past conversations
- ✓ From known colleague, client, or business contact
- ✓ Asks a question or requests a decision
- ✓ Personalized content (uses your name)
- ✓ Time-sensitive (deadline, urgent)

**Examples:**
```
From: partner@example.com
Subject: "Project doc - can you review by Friday?"
Body: "Hi, I've updated the website content brief. Need your feedback on the design section..."

Classification: IMPORTANT (95% confidence)
Reason: Known contact, specific project reference, asks for decision, personalized
Action: Respond within 24 hours
```

```
From: client@example.com
Subject: "Project update - new requirements"
Body: "The client just added 3 new features to scope. See attached..."

Classification: IMPORTANT (92% confidence)
Reason: Client contact, project-specific, affects your work
Action: Review and respond
```

**Confidence Threshold:** 85%+

**Mark as read?** NO — Keep unread to force action

---

### 2️⃣ UPDATES — Automated Service Notifications

**Definition:** System notifications, service alerts, and automated messages from companies

**Characteristics:**
- ✓ From a known service/company (GitHub, Google, AWS, etc.)
- ✓ No-reply address (noreply@, notifications@, alerts@, etc.)
- ✓ Generic greeting ("Hello", "Hi there", not personalized)
- ✓ Automated/templated format
- ✓ Contains status, confirmation, or notification info
- ✓ No action required (informational only)

**No-reply senders that are ALWAYS UPDATES:**
- noreply@*
- no-reply@*
- donotreply@*
- notifications@*
- alerts@*
- updates@*
- news@*
- mailer-daemon@*
- bounce@*

**Examples:**
```
From: noreply@accounts.google.com
Subject: "Security alert: New sign-in from Mac"
Body: "Your Google Account was accessed from a Chrome browser on Mac (California)..."

Classification: UPDATES (98% confidence)
Reason: No-reply address from Google (known service), security notification
Action: Verify you, then ignore/archive
```

```
From: notifications@github.com
Subject: "[PR] Your pull request was merged"
Body: "The PR #123 in repo/name was merged by reviewer..."

Classification: UPDATES (96% confidence)
Reason: No-reply from GitHub (known service), automated notification
Action: No action needed
```

```
From: invoice@mail.anthropic.com
Subject: "Invoice #2788-9023-3336 ready"
Body: "Your invoice for Claude API usage is ready..."

Classification: UPDATES (94% confidence)
Reason: Automated billing notification from known company
Action: Review if needed, then archive
```

**Confidence Threshold:** 90%+

**Mark as read?** YES — These don't need your attention

---

### 3️⃣ SHARED-DOCS — Document Collaboration & Sharing

**Definition:** Invitations to view, edit, or collaborate on documents

**Characteristics:**
- ✓ Contains sharing invitation or link
- ✓ From Google Drive, Dropbox, OneDrive, Notion, etc.
- ✓ Mentions "shared with you", "invited to edit", "access granted"
- ✓ Contains document/folder name
- ✓ Usually from no-reply address of sharing service

**Sharing Services:**
- Google Drive/Docs/Sheets/Slides
- Dropbox
- OneDrive
- SharePoint
- Notion
- Figma
- Canva
- Asana
- Monday.com
- Any project management tool

**Examples:**
```
From: drive-shares-dm-noreply@google.com
Subject: "Dyke shared AutomateIX: Website Content & Design Brief"
Body: "You have been invited to edit the document. Open document ↓"

Classification: SHARED-DOCS (94% confidence)
Reason: Google Drive share notification
Action: Review document, provide feedback, may need action
```

```
From: notifications@dropbox.com
Subject: "John shared 'Q1_Budget' folder with you"
Body: "John (john@company.com) shared a folder with you..."

Classification: SHARED-DOCS (90% confidence)
Reason: Dropbox share notification
Action: Review folder contents
```

```
From: figma-noreply@figma.com
Subject: "Sarah invited you to Prototype v2"
Body: "You've been invited to a Figma file..."

Classification: SHARED-DOCS (88% confidence)
Reason: Figma collaboration invite
Action: Review design, provide feedback
```

**Confidence Threshold:** 88%+

**Mark as read?** YES — But keep in a special label for reference

---

### 4️⃣ SPAM — Junk & Promotional Emails

**Definition:** Unsolicited marketing, junk, and suspicious emails (80%+ confidence only)

**Characteristics:**
- ✗ From unknown sender or company
- ✗ Marketing/promotional language
- ✗ Subject: ALL CAPS, excessive punctuation, urgency
- ✗ Generic greeting ("Dear User", "Dear Sir/Madam")
- ✗ Requests money, credentials, or personal info
- ✗ Grammar/spelling errors (red flag!)
- ✗ "Unsubscribe" link present

**Red Flag Phrases:**
- "Act NOW!"
- "FINAL WARNING"
- "Limited time offer"
- "Exclusive deal"
- "You've won!"
- "Claim your prize"
- "Urgent action required"
- "Verify your account"
- "Update payment info"

**Red Flag Senders:**
- Random strings: "xjk2@mail123.com"
- Misspellings: "goog1e@gmail.com", "amaz0n@..."
- Free email claiming to be business: "company@gmail.com"
- Unknown TLDs: "company@.xyz", "offer@.ru"

**Examples:**
```
From: promo@marketingsite.example
Subject: "⚠️ AI BOOT CAMP - ENDS TONIGHT!! 🚀"
Body: "Feel like the world is moving too fast? Limited spots, $199 only!"

Classification: SPAM (88% confidence)
Reason: All caps subject, urgency language, promotional, unsolicited
Action: Unsubscribe or archive
```

```
From: urgent.winner@weirdomain.ru
Subject: "⚠️ YOU'VE WON $1 MILLION!!"
Body: "Click here to claim your prize! Confirm payment info..."

Classification: SPAM (99% confidence)
Reason: Classic scam language, suspicious domain, requests payment
Action: Delete, never reply
```

```
From: mail.grammarly.com
Subject: "Black Friday - 50% OFF Grammar Checker!"
Body: "Limited time: Save 50% on Grammarly Premium..."

Classification: SPAM (82% confidence)
Reason: Marketing email, unsolicited offer, urgency tactics
Reason: (Note: From known company, so confidence is lower than other spam)
Action: Unsubscribe (one-click link provided) or archive
```

**Confidence Threshold:** 80%+ (STRICT!)

**Default on uncertain?** NO — Default to UPDATES (safer to keep than delete)

**Mark as read?** YES — And skip inbox (archive)

---

## Decision Rules (Applied in Order)

**These rules help classify tricky emails:**

### Rule 1: Known Domains = Never SPAM
```
If sender domain is: google.com, github.com, github.io,
                     slack.com, aws.amazon.com, stripe.com,
                     anthropic.com, etc.
Then: NEVER classify as SPAM (at worst, UPDATES)
```

### Rule 2: No-Reply = Never IMPORTANT
```
If sender contains: noreply@, no-reply@, notifications@, etc.
Then: Classify as UPDATES or SHARED-DOCS, never IMPORTANT
```

### Rule 3: Share Invitation = Always SHARED-DOCS
```
If email contains: "shared with you", "invited to edit",
                   "access granted", doc/folder links
Then: SHARED-DOCS (high confidence)
```

### Rule 4: Uncertain Between SPAM and Other
```
If confidence in SPAM < 85% AND uncertain about category
Then: Default to UPDATES (safer to keep than delete)
```

### Rule 5: Thread Reply = Likely IMPORTANT
```
If email is a reply in existing thread (In-Reply-To header)
Then: Lean toward IMPORTANT (human conversation)
```

### Rule 6: Marketing from Known Company = UPDATES
```
If email is marketing BUT from company you use/subscribe to
Then: UPDATES, not SPAM
Example: Claude pricing announcement = UPDATES
Example: Random MLM offer = SPAM
```

---

## Confidence Scoring

Each classification gets a confidence score (0-100%):

| Score | Meaning | Action |
|-------|---------|--------|
| 95-100% | Certain | Apply label confidently |
| 85-95% | Very confident | Apply label |
| 75-85% | Confident | Apply label (for SPAM, 80%+ required) |
| 65-75% | Somewhat confident | Manual review recommended |
| <65% | Uncertain | Don't classify (wait for more info) |

**Minimum Thresholds:**
- IMPORTANT: 85%
- UPDATES: 90%
- SHARED-DOCS: 88%
- SPAM: 80% (strict - false positive is bad)

---

## Special Cases

### Marketing from Services You Use
```
MindStudio promotional email (you use MindStudio)
→ UPDATES (not SPAM) - you subscribed to it

Grammarly Black Friday deal (you use Grammarly)
→ UPDATES (not SPAM) - expected marketing
```

### Receipts & Invoices
```
Amazon order confirmation
→ UPDATES (automated notification)

Invoice from service you use
→ UPDATES (billing notification)
```

### Calendar & Meeting Invites
```
"You're invited to meeting" from Outlook/Google Calendar
→ UPDATES (automated calendar notification)
```

### Password Reset Emails
```
"Reset your password" from Google/GitHub/etc
→ UPDATES (security notification)
```

### Multi-Part Messages
```
Email with both personal content + marketing
→ If personal part is substantial: IMPORTANT
→ If personal part is minimal: UPDATES
```

---

## Testing Your Rules

### Test Case 1: Client Email
```
From: client@company.com
Subject: "Can you adjust the timeline?"
Body: "Hi, project scope just changed. See attached doc..."
Expected: IMPORTANT (98%)
Why: Known contact, asks question, project-specific
```

### Test Case 2: GitHub Notification
```
From: notifications@github.com
Subject: "[natehoward/project] PR #42 merged"
Body: "Your PR was merged by reviewer..."
Expected: UPDATES (96%)
Why: No-reply from known service, automated notification
```

### Test Case 3: Google Drive Share
```
From: drive-shares-dm-noreply@google.com
Subject: "Team shared Q1 Planning with you"
Body: "You can now access the document..."
Expected: SHARED-DOCS (92%)
Why: Google Drive share notification
```

### Test Case 4: Promotional Email
```
From: marketing@promosite.example
Subject: "⚠️ SPECIAL OFFER ENDS TODAY!"
Body: "Limited spots in our AI boot camp, $199!"
Expected: SPAM (85%)
Why: All caps subject, urgency language, unsolicited marketing, unknown to user
```

---

## When to Override

You can override automated classification if:
- Email is clearly misclassified
- Rules changed (new client domain to add)
- New service to recognize

Tell Claude: "I got an email from [sender] with subject '[subject]' — it should be [CATEGORY]"

Claude will remember for future emails.

---

## Summary Table

| Category | From | Tone | Action | Mark Read? |
|----------|------|------|--------|-----------|
| IMPORTANT | Known person | Conversational, personal | Respond | NO |
| UPDATES | Known service | Automated, generic | Acknowledge | YES |
| SHARED-DOCS | Sharing service | Invitation, link | Review & feedback | YES |
| SPAM | Unknown/unsolicited | Promotional, generic | Delete/unsub | YES |

---

**Questions?** See [README.md](../README.md) or [TROUBLESHOOTING.md](../TROUBLESHOOTING.md)
