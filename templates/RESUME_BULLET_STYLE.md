# Resume bullet style guide

This is the contract every resume bullet must satisfy. Agents that produce
bullets (bullet-writer, resume-builder) follow these rules. The
resume-validator agent checks them on every output.

## Shape

Every bullet has this shape:

  [Strong verb] [concrete object] [(technology where relevant)] [impact metric]

Examples that pass:
  Built 6 Java-based ETL jobs processing over 1 million records daily with 99.9% data accuracy.
  Cut API response size from ~5 MB to ~87 KB (98% reduction) via field selection and geometry simplification.
  Led a team of 3 mobile developers shipping a React Native consumer product with 99+ commits across 15+ feature branches.

Examples that fail:
  Passionate about building scalable systems.   (no verb, no scope, buzzword)
  Worked on the backend, did some optimizations.   (vague verb, no metric)
  Leveraged various technologies to drive impact.   (banned verb, banned object)

## Length cap

Maximum 25 words per bullet. If you can't fit, you have two bullets,
not one. The whole resume is two pages maximum.

## Verb rules

Strong verbs only. First word of every bullet.

GOOD verbs:
  Built, Architected, Shipped, Designed, Implemented, Cut, Refactored,
  Owned, Led, Integrated, Optimized, Established, Drove, Scaled,
  Migrated, Hardened, Automated, Reduced, Eliminated, Launched.

BANNED verbs:
  Utilized, Leveraged, Helped with, Worked on, Was responsible for,
  Contributed to, Participated in, Was involved in, Assisted with,
  Took part in, Supported.

If you find yourself reaching for a banned verb, the underlying claim
is probably too soft to be on the resume.

## Metric or scope rule

Every bullet should answer one of:
  - What's the number a recruiter remembers? (perf, scale, users, accuracy)
  - What's the scope they should picture? ("4 enterprise applications",
    "3 product surfaces", "13 feature modules")

If you can't quantify, qualify with concrete scope. Never write a bullet
that's just "made things better."

## Buzzword blocklist

Never appear in bullets, summary, or skills:

  passionate, leverage / leveraged / leveraging, synergize / synergy,
  utilize / utilized, dynamic, results-driven, go-getter, self-starter,
  team player, strong communicator, hard worker, motivated, energetic,
  detail-oriented (use the actual detail instead), proven track record,
  thought leader, ninja, rockstar, guru, world-class, best-in-class.

The skills section may use industry-standard compound terms (e.g.
"event-driven architecture") even if they contain a banned word.

## Honesty before polish

Style rules never override the honesty rules in RESUME_HONESTY.md.
If a bullet has to be slightly less polished to be accurate, it stays
accurate. Style is the second-order concern.

## Page limit

Resume is 2 pages maximum. If a tailor pushes over:
  1. Cut the oldest job's bullets first (down to 2 lines)
  2. Cut the weakest project (move to a future variant in content/)
  3. Compress the skills section (combine related rows)
  4. Never cut Education, Publications, or the lead project
