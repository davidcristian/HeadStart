/** Marketing landing page static content. */

export const INTEGRATIONS = [
  "Greenhouse",
  "Lever",
  "Ashby",
  "Workday",
  "Indeed",
  "LinkedIn",
  "Slack",
  "ntfy",
];

export const STEPS = [
  {
    step: "1",
    title: "Connect the boards you watch",
    body: "Add company career pages and job sites, or paste a job-board URL and let HeadStart detect the source for you.",
  },
  {
    step: "2",
    title: "Filter before you get pinged",
    body: "Keywords, location, workplace, salary, and cross-search dedup so you only hear about roles worth your time.",
  },
  {
    step: "3",
    title: "Apply while others are scrolling",
    body: "Instant alerts via ntfy, email, Slack, Discord, Telegram, or your own webhook — plus AI summaries of why each role fits.",
  },
];

export const FEATURES = [
  {
    title: "Always watching",
    body: "HeadStart polls your sources on a schedule and catches new postings the moment they go live.",
  },
  {
    title: "Your channels, your rules",
    body: "Immediate pings or batched digests. Route alerts wherever you already live — phone, inbox, or team chat.",
  },
  {
    title: "Built for speed",
    body: "Mobile PWA, RSS export, and a focused jobs feed so you can review and act from anywhere.",
  },
];

export const SHOWCASE = [
  {
    id: "searches",
    label: "Searches",
    title: "Configure watches with confidence",
    body: "Structured filters, scrape health, and a one-click test run so you know a search works before you wait on the poll interval.",
    image: "/marketing/searches.png",
    alt: "HeadStart searches page showing filter form and a healthy enabled search",
  },
  {
    id: "jobs",
    label: "Jobs feed",
    title: "Triage matches in one place",
    body: "Review new roles, mark seen or applied, filter by search, and export an RSS feed for your own tools.",
    image: "/marketing/jobs.png",
    alt: "HeadStart jobs feed with salary, status badges, and triage actions",
  },
  {
    id: "alerts",
    label: "Alerts",
    title: "Get pinged the moment it posts",
    body: "Push to ntfy, email, Slack, Discord, Telegram, or a signed webhook — each alert includes an AI summary of why the role fits.",
    image: "/marketing/notification.png",
    alt: "Example ntfy notification for a new Senior Backend Engineer match",
  },
] as const;

export const FAQ = [
  {
    q: "How is HeadStart different from job board alerts?",
    a: "Board alerts are broad and noisy. HeadStart watches the specific sources you choose, applies your filters server-side, deduplicates across searches, and pushes only net-new matches.",
  },
  {
    q: "Do I need to keep a tab open?",
    a: "No. HeadStart runs in the cloud on a schedule. You get notified even when your laptop is closed.",
  },
  {
    q: "Which sites are supported?",
    a: "Greenhouse, Lever, Ashby, Workday, Indeed, LinkedIn, and generic HTML career pages — with more adapters added over time.",
  },
];
