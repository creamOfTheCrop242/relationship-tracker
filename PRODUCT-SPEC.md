# So About Us Product Specification

## Product purpose

So About Us is a private, personal relationship journal. It helps one user record relationship events, track personal and perceived partner needs, review patterns over time, and receive AI-generated reflections.

The first version is for one user only. Partner access may be added later.

The app should help the user notice patterns and take thoughtful action. It should not turn the relationship into a competition, diagnose either person, or present an AI score as objective truth.

## Visual direction

The app should feel like a warm, calm, private journal rather than a clinical dashboard or a gamified scorecard.

Visual direction:

- Warm cream background: `#F7F1E8`
- White cards: `#FFFFFF`
- Terracotta primary accent: `#E06F52`
- Deep charcoal text: `#292622`
- Soft sage for positive states: `#A8C3A0`
- Warm gold for needs attention: `#E5B85C`
- Muted rust for conflict states: `#B96955`
- Soft lavender for private or personal states
- Gently rounded cards and controls
- Generous spacing and readable typography
- Light mode first, with optional dark mode later

Score cards should use a calm information treatment rather than aggressive red or green performance indicators. They should show the score, confidence, trend, and explanation together.

## Initial product decisions

- The app is private to one user initially.
- The user signs in with Google or Apple through custom OAuth handled by FastAPI.
- All entries are owned by the authenticated user.
- The partner does not need an account in the first version.
- The partner can be represented as “Partner.”
- Entries can be backdated.
- Notes are optional.
- The user’s local timezone controls dates and scheduled analysis.
- The app is mobile-first and installable as a Progressive Web App.
- The user can export or delete their data.

## Authentication architecture

The app will not use Netlify Identity for the initial authentication flow. Netlify Identity’s default provider branding is not the desired app experience, and custom Identity OAuth is not part of the current cost plan.

Instead, the app will use a custom OAuth flow modeled after the Chess Sagas implementation:

```text
React app
  → Netlify same-origin API proxy
    → FastAPI on Heroku
    → Google or Apple OAuth
      → Heroku Postgres
        → Secure session cookie
```

Heroku Postgres is the application database and is independent of the authentication provider. Netlify hosts the frontend and proxies API requests.

The authentication backend will:

- Generate Google and Apple authorization URLs.
- Use unpredictable state values to protect against CSRF.
- Handle OAuth callbacks.
- Exchange authorization codes for provider tokens.
- Validate provider identity claims.
- Create or find the application user.
- Store provider identifiers separately from the application user ID.
- Create and revoke secure server-side sessions.
- Protect all authenticated database operations.

The application should keep its own user record and ownership IDs so a future provider change does not require rebuilding event, needs, summary, or task data.

Google OAuth credentials are required. Apple web authentication requires an Apple Developer account, a Services ID, a private key, and HTTPS callback URLs.

## Event tracking

Events describe what happened. The app uses one quick event form that changes based on the selected category.

Shared event fields:

- Category
- Date and time
- Person involved: me, partner, both, or neither
- Optional mood
- Optional impact
- Optional notes
- Created and updated timestamps

Only the category, date, and basic event description should be required. The rest should remain optional so logging stays quick.

### Event categories

#### Intimacy

- Type: sex, kissing, cuddling, affection, emotional closeness, or custom
- Optional satisfaction rating
- Optional notes

#### Kindness and connection

- What happened
- Who initiated it
- Optional appreciation rating
- Optional notes

#### Conflict

- Who was upset: me, partner, or both
- Who initiated the conflict, if known
- What caused it
- Whether it was resolved
- Optional intensity rating
- Optional notes

#### Going out

- Activity
- Who attended
- Optional enjoyment rating
- Optional notes

#### Alcohol

- Who drank
- Broad level: light, moderate, or heavy
- Optional context or notes

#### Childcare

- Who provided care
- Approximate duration
- Whether the arrangement felt fair
- Optional notes

#### Custom event

- Event title
- Description
- Optional rating
- Optional notes

## Relationship needs

Needs describe what matters to the user or what the user believes matters to their partner. Need updates describe how a need was met on a particular date.

Examples:

- Quality time
- Physical affection
- Appreciation
- Emotional support
- Better communication
- Help with childcare
- Reliability
- Personal space
- Intimacy

### Need fields

- Person: me or partner
- Need name
- Description
- Why it matters
- Importance: low, medium, or high
- Desired amount
- Desired period: per day, per week, per month, custom period, as needed, or no target
- Confirmed by partner: yes, no, or unknown
- Active or archived status
- Created and updated timestamps

The desired cadence describes what the user wants from the relationship. It is not an obligation or quota.

Examples:

- Sex: 2 times per week
- Quality time: 1 time per day
- Date night: 3 times per month
- Emotional support: as needed

### Need updates

- Date
- Status: met, partly met, or not met
- What happened
- Satisfaction rating
- Optional notes
- Created and updated timestamps

For partner needs, the app must distinguish the user’s interpretation from something the partner directly confirmed. Unconfirmed partner needs should be treated as observations or hypotheses, not facts.

### Linking needs to events

Needs can optionally connect to matching event types:

- Sex → Intimacy: sex
- Quality time → Going out or connection
- Affection → Intimacy: affection
- Childcare support → Childcare
- Appreciation → Kindness and connection

The user can still manually update a need when an event does not fit neatly into a category.

The app can compare logged events against a desired cadence:

```text
This week: 1 of 2 recorded
Progress: Below desired cadence
```

The app should say “no entry recorded” instead of assuming an activity did not happen.

## Dashboard

The dashboard should show:

- Last intimacy
- Last kind gesture
- Last argument
- Last time either person was upset
- Last outing
- Last drinking event
- Recent childcare activity
- Current relationship needs
- Needs with low recent satisfaction
- Needs that have not been updated recently
- Needs trending better or worse
- Recent events
- The latest daily reflection
- A prominent “Log something” action

The dashboard should provide context without judging the relationship.

## AI analysis

The user can control AI analysis with one global setting:

```text
AI relationship analysis: On / Off
```

There are no per-entry AI inclusion controls. When analysis is on, all eligible events and need updates are included. This prevents selectively excluding positive or negative entries to skew results.

When analysis is off:

- No new OpenAI analysis is generated.
- Events and needs continue to be tracked normally.
- Existing summaries remain unless the user deletes them.

The app should show data coverage because users can still forget to log events:

```text
Data coverage: 5 of 7 days recorded
Events analyzed: 14
Need updates analyzed: 6
Confidence: Medium
```

Missing data should remain missing, rather than being treated as positive or neutral.

### Score design

The app uses a structured scoring approach. The AI generates the score and interpretation, but the inputs and factors remain consistent.

The score:

- Uses a range of 0–100.
- Includes a confidence level: low, medium, or high.
- Shows “Not enough data” when the period is too sparse.
- Does not allow one event to determine the entire result.
- Does not assume that more sex, drinking, or outings automatically means a healthier relationship.

Potential factors include:

- Positive connection events
- Kindness and support
- Needs met
- Needs unmet
- Resolved conflicts
- Unresolved conflicts
- Mood ratings
- Childcare balance
- Data coverage
- Recent trend compared with an earlier period

### AI output

Every reflection should separate:

1. **What the data shows**
2. **Interpretation**
3. **Suggested next steps**

The AI should return:

- Score from 0–100
- Confidence level
- Positive factors
- Friction factors
- What the patterns may mean
- Comparison with previous periods
- Unresolved issues
- One or two optional suggested actions
- Short plain-language reflection
- Missing information or limitations

Example:

```text
Score: 78
Confidence: Medium

What the data shows:
You recorded more positive connection this week than last week. Your quality-time need was met, but childcare support was rated low twice.

Interpretation:
The relationship appears to have had more intentional connection, while practical responsibilities may still be creating stress.

Suggested next step:
Consider discussing how childcare responsibilities are feeling before the issue becomes a recurring source of conflict.
```

The tone should be supportive, neutral, and direct. Suggestions must be optional, nonjudgmental, and careful about unconfirmed assumptions.

The OpenAI API call happens inside the protected FastAPI service on Heroku. The API key remains in a private Heroku environment variable and is never included in frontend code. Requests use structured output and disable OpenAI response storage.

## Period summaries

The app should support daily, weekly, monthly, and yearly summaries.

Each summary should include:

- Average or generated score
- Score range and trend
- Confidence
- Data coverage
- Most positive patterns
- Most common friction points
- Needs consistently met
- Needs frequently unmet
- Unresolved conflicts
- Notable changes from the previous period
- A written reflection
- One or two optional suggested actions

Summaries should be based on the period’s actual events and need updates, not only an average of previous AI scores.

### Summary timing

- Daily analysis runs the following morning, by default at 3:00 AM local time.
- It analyzes the previous local calendar day so late-night entries are included.
- Weekly analysis runs after the week ends.
- Monthly analysis runs after the month ends.
- Yearly analysis runs after the year ends or on demand.
- Any period can be regenerated manually after older entries are edited.

## Reminders and relationship actions

The app should support reminders based on needs and AI suggestions.

### Cadence reminders

When a need has a desired cadence and not enough matching entries have been recorded, the app can remind the user.

Example:

```text
Need: Quality time
Desired cadence: Once per week
Recorded this week: 0
```

Reminder:

> No quality-time entry has been recorded this week. Would you like to plan something?

### AI suggestions

The app can periodically suggest small optional actions based on needs and recent patterns:

- Send a sweet text
- Plan a date
- Give a massage
- Express appreciation
- Ask how the partner is doing
- Discuss an unresolved issue

Suggestions should be limited so they do not become annoying.

### Pending relationship tasks

A suggestion can become a task:

```text
Suggested action: Give your partner a massage
Due: Today
Status: Pending
Source: AI suggestion
Related need: Physical affection
```

When the user clicks a notification:

1. The app opens the pending task.
2. The user can complete, reschedule, snooze, dismiss, or edit it.
3. When completed, the app offers to log what happened as an event.
4. The event can link back to the need that generated the suggestion.

Supported task statuses:

- Pending
- Completed
- Snoozed
- Dismissed

Reminder settings should control:

- Whether reminders are enabled
- Which needs can generate reminders
- Reminder timing
- How often AI suggestions appear
- Whether completed tasks prompt event logging

## Initial database concepts

### `users`

Stores the authenticated user relationship.

### `events`

Stores relationship events and their details.

### `relationship_needs`

Stores personal or perceived partner needs, desired cadence, importance, and confirmation status.

### `need_updates`

Stores dated updates about whether a need was met and how satisfying it was.

### `daily_reflections`

Stores daily AI scores, confidence, coverage, factors, interpretation, and suggestions.

### `relationship_summaries`

Stores weekly, monthly, and yearly summaries.

### `relationship_tasks`

Stores cadence reminders and AI-suggested relationship actions.

## Phased implementation plan

### Phase 0: Product definition

Finalize the event categories, need fields, desired cadence behavior, score design, summary behavior, AI privacy setting, reminder behavior, and notification preferences.

### Phase 1: Project foundation

Set up React, TypeScript, Vite, the PWA structure, GitHub, Netlify deployment, and the base application layout.

### Phase 2: Custom authentication

Set up custom Google and Apple OAuth through FastAPI, secure session cookies, provider identity mapping, protected routes, session handling, and single-user access.

### Phase 3: Database and backend

Create the PostgreSQL schema, Alembic migrations, FastAPI endpoints, authenticated operations, and ownership checks.

### Phase 4: Event tracking

Build quick event entry, category-specific fields, timeline, filtering, search, editing, deletion, and backdating.

Event tracking provides an optional partner name (default “Partner”), one private relationship per user, and entries with category, description, date/time, optional person, mood, impact, and notes. A relationship is created automatically on the first entry or when saving the partner name. Entries support editing, deletion, backdating, and a paginated timeline. Dates are entered and displayed in the device's local timezone and stored as timezone-aware timestamps. The form shows validated fields for each category, including ratings and category-specific context. The timeline supports combined text, category, person, and local date-range filters while preserving pagination. Adding a partner name grants no shared access.

### Phase 5: Relationship needs

Build adding and editing needs, archiving, desired cadence tracking, dated need updates, satisfaction ratings, and need history.

Relationship needs identify whether the need belongs to the user or reflects the user's understanding of their partner. Partner needs show whether the partner directly confirmed them. Each need supports importance, explanatory context, active or archived status, and either no target, an as-needed cadence, a daily/weekly/monthly target, or a custom number of days. Dated updates record met, partly met, or not met status, what happened, a 1–5 satisfaction rating, optional notes, and editable history. Cadence is presented as a preference rather than an obligation, and missing updates remain unknown.

A broad need can contain multiple specific requests. For example, “love and consideration” can include “a daily foot rub,” while “sexual connection” can include “receive a nude once per day.” Each request has its own cadence, confirmation status, active state, reminders, and generated tasks. When active request cadences exist, reminders follow those concrete requests instead of treating the broad need itself as the requested action.

Each journal entry can optionally link to a broad need and one of that need's specific requests. The timeline shows the association, and a linked entry counts as recorded activity toward the selected request's cadence. Entries remain valid without a need association.

### Phase 6: Dashboard

Build last-time cards, recent activity, current needs, trend views, low-satisfaction indicators, and the latest reflection.

The deterministic dashboard shows the latest recorded intimacy, kindness, conflict, outing, drinking, childcare, and upset events; five recent events; and active need summaries. A need is flagged for low recent satisfaction when its latest rating is 1 or 2, and as stale when it has no update or its latest update is more than 14 days old. After four dated updates, the trend compares the average of the latest two satisfaction ratings with the previous two; a difference of at least 0.5 is shown as improving or declining, otherwise it is steady. These signals describe recorded data only and do not judge overall relationship health. The latest AI reflection remains part of Phase 7.

### Phase 7: OpenAI reflections

Build scheduled analysis, manual regeneration, structured AI output, daily reflections, period summaries, confidence, and data coverage.

AI analysis is off by default and can be changed with one global privacy control. Daily, weekly, monthly, and yearly results share one persisted period-summary model, including the score, confidence, coverage, factors, interpretation, comparison, unresolved issues, optional actions, reflection, and limitations. Fewer than two recorded events or need updates produces a coverage report with no score and makes no model request. Manual generation supports any date within a period. An hourly trusted scheduler checks each enabled user's local timezone after 3:00 AM and generates completed daily periods plus weekly, monthly, and yearly periods when due. Existing reflections remain readable when analysis is turned off and can be deleted by the user.

An opted-in user can also ask one relationship question at a time. The model receives the question plus a bounded set of that user's recent events and need updates, returns a grounded perspective with optional next steps and limitations, and does not save the question or answer. Advice must avoid diagnosis, blame, certainty about a partner's motives, and medical or legal guidance; possible immediate danger, abuse, or self-harm receives safety-first guidance.

### Phase 8: Privacy, backups, and reliability

Add authentication checks, secure API key storage, data export, deletion, error handling, duplicate-analysis protection, timezone handling, and AI settings.

The account privacy controls provide a complete JSON export of the signed-in user's profile, connected sign-in providers, relationship, events, needs and updates, and saved reflections without exporting session tokens. Permanent account deletion requires explicit confirmation, removes the user and all related records through database cascades, clears the browser session, and never affects another user's data.

### Phase 9: Mobile experience

Add PWA installation, touch-friendly forms, fast logging, push notifications, reminder controls, task deep links, loading states, accessibility, and offline-friendly drafts.

Progress:

- Installable PWA shell, app icons, standalone display, and offline app loading implemented.
- Quick-log app shortcuts and category deep links implemented.
- Journal entry drafts persist on the device and restore after an interruption or lost connection.
- Offline status, network-aware errors, safe-area layout, touch targets, reduced-motion support, and mobile dialog actions implemented.
- Persisted relationship tasks support manual actions and cadence or AI sources, with complete, edit, reschedule, snooze, dismiss, and reopen flows.
- Reminder controls include per-need cadence eligibility, reminder hour, daily, weekly, or monthly AI suggestion frequency, and completed-task logging prompts. At the selected hour, an enabled AI frequency makes a fresh API request using private profiles, active needs and requests, recent events, and recent tasks, then saves one optional action as a task. The prompt excludes requests already covered by automatic cadence and avoids recent task repetition.
- Web Push subscriptions, hourly delivery, and notification task deep links are implemented. Deployment requires VAPID keys before device notifications can be enabled.

### Phase 10: Personal testing

Use the app for several weeks to evaluate logging speed, useful categories, needs tracking, score quality, AI reflections, reminders, and missing features.

Personal testing additions:

- Private profiles for the user and partner capture love languages, hobbies, interests, goals, and freeform context.
- Each profile shows that person's active relationship needs alongside their personal context.
- Partner profile information remains the user's private understanding unless future partner access explicitly confirms it.

### Phase 11: Optional partner access

Add partner invitations, private and shared entries, separate ownership, shared needs, shared reflections, permissions, and visibility controls only after the personal version proves useful.
