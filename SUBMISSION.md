# Winner Signal — hackathon submission draft

Event: Gemini 4 Argon SF Hackathon · October 25, 2026

**Draft status:** Deployed prototype at https://winner-signal.vercel.app. Link-first gallery, feedback, repository snapshots, optional history ingestion and a YouTube analytics connector are implemented. Owner-authorized YouTube API retrieval has been verified; today’s reports may still be pending. Training gains have not been demonstrated. Gemini video-to-code review was tested on a controlled uploaded clip; a public YouTube URL review path is now implemented and tested; a live Gemini URL probe succeeded on Google’s public example, while an updated live review of our own uploaded demo, pinned code and a curated build-history excerpt succeeded with five video claims, six cited trace findings, and a verified evidence seal. The own-demo YouTube-URL review is still not separately verified. Public repository: https://github.com/LEE-CHENYU/winner-signal. Demo video: https://youtu.be/m-gMjoL5yew. The official hackathon form has not been submitted.

## Team Name*

Winner Signal

## Team Members

Use the approved members selected in the organizer's form. The pasted form displays “chenyusu” and “Cheney Li”; confirm the final selection there rather than creating duplicate entries.

## Project Description*

**Winner Signal connects AI-assisted work to evidence of what its outputs do in the real world, with the goal of building better signals for AI evaluation and training.**

A benchmark pass rate tells us whether an agent met a test's criteria. It does not, by itself, establish whether the resulting product works for people or creates useful value. We want to connect the building process, the resulting artifact, and observed outcomes so that future evaluation and training can reward useful work.

Our first setting is AI-assisted hackathon projects. Builders already have a demo, public code and often a coding-agent session. Winner Signal gives them a public gallery to find initial viewers and a private evidence workspace to return to. They add a hosted demo link and repository; optional session exports provide context about the actions, edits and tests behind the result.

We collect distinct signals: audience engagement from authorized YouTube analytics, visits and outbound clicks on Winner Signal, and viewer questions, feedback and stated interest. These are early observations of audience response, not proof of adoption or economic value. The YouTube connector checks that the authorized channel owns the submitted video and keeps host reports separate from our own activity counts.

A complementary Gemini 4 Argon prototype connects timestamped video claims to commit-pinned code and suggests follow-up tests. It distinguishes what a demo shows from what source code supports and what remains unverified. This review was tested on a controlled uploaded clip. The new link path supports public YouTube demos up to two minutes after uploader verification; its queue, citation validation and evidence sealing pass an integration test with a stubbed model response, and a separate live Gemini URL probe succeeded on Google’s public sample.

The longer-term research question is: **which observable outcomes of AI-assisted work provide reliable feedback for improving the agents that produced it?** With explicit participant permission, we aim to connect build trajectories and versioned artifacts to subsequent outcomes, then test candidate training signals against held-out real-world results. We have not trained a model on participant data or demonstrated training improvement.

For builders, the immediate benefit is viewers and actionable feedback. For AI research, this is a first step toward measuring the usefulness of actual outputs beyond test pass rates.

## Public Project GitHub Repository*

https://github.com/LEE-CHENYU/winner-signal

Before submitting: verify the repository is public and contains the actual build, setup instructions, and clear attribution for reused AERead infrastructure. Exclude secrets, private uploads, and `session-history/`.

## 1-Minute Demo Video*

https://youtu.be/m-gMjoL5yew

Before submitting: verify playback while signed out and keep the video within the form's one-minute requirement. Show the actual implemented workflow; label any fixture data or simulated outputs.

## Describe your use of Google products to build the submitted project:*

We use Gemini 4 Argon (`gemini-4-argon`) through the Google Gen AI Python SDK and Gemini API for a video-to-code evidence-review prototype. It analyzes an uploaded clip alongside a bounded, commit-pinned source snapshot, produces timestamped observations and source references, and suggests further tests. Optional redacted session exports can be included with consent. The pipeline supports uploaded assets and public YouTube links up to two minutes, with uploader verification and explicit review consent. Private or unlisted URLs are not supported for review.

The pipeline uses the Files API, token counting, bounded generation, JSON output and local validation. Source-line and timestamp bounds are checked, and artifacts are sealed using a reused, pinned AERead evidence layer. A live review and queued worker review were verified on a controlled test clip. These checks establish integration, not accuracy across arbitrary projects or usefulness as a training reward.

We use Google sign-in and the YouTube Data and Analytics APIs to connect a builder's authorized channel with a specific demo. Sign-in requests optional read-only YouTube permission and connects the same account when granted; builders can connect a different uploader account if needed. The connector supports private video-level reports including views, watch time and average viewing duration. The OAuth app remains in Testing mode, and owner-authorized video report retrieval has been validated.

No Managed Agents integration is claimed. Gemini API access is separate from the Antigravity subscription.

## Do you have any feedback for the Google Deepmind team on Argon?*

Our use case makes evidence attribution especially important: a useful review must distinguish something visible in a video, a narrator's assertion, a plausible code path, and a successfully observed execution. We'd value strong timestamp grounding and source-linked structured outputs across video and code, with clear uncertainty when the connection cannot be established. Predictable latency and cost for reviewing a short demo alongside a bounded repository would also help this workflow scale.

During integration, plain video generation succeeded, while the tested provider-enforced schema requests returned HTTP 400. JSON mode plus local validation worked. More actionable schema error messages would have shortened debugging. This is a bounded integration observation, not a general claim about Argon accuracy or schema support.

---

## Suggested one-minute demo storyboard

This is a recording plan, not a record of completed functionality. Use only implemented screens and actual outcomes.

| Time | Show | Suggested narration |
| --- | --- | --- |
| 0–8s | Gallery | “Passing a benchmark doesn't tell us whether an AI-built product is useful. We want to measure what happens to the actual output.” |
| 8–20s | Link-first submission and repository | “Builders share a demo and code, with optional build history. The gallery helps them find their first viewers.” |
| 20–34s | Dashboard and YouTube connection status | “We connect audience response to each project: engagement, feedback and authorized video analytics. Show only real reports; if none are available, show the pending connection honestly.” |
| 34–47s | Clearly labeled controlled Gemini review | “Our separate review prototype checks a demo's claims against its code and identifies what still needs testing. Public YouTube link review is now implemented; label any prerecorded or controlled result.” |
| 47–60s | Dashboard and next-version action | “Our goal is to connect how AI helped build something with whether the result works and gets used, then test which signals improve AI training. This prototype starts collecting the evidence.” |

Do not fabricate the mock-booking finding: use a clearly labeled controlled example with that actual implementation. Pre-run analysis is acceptable if shown as a recorded result rather than disguised as a live call. Never manufacture audience counts; demonstrate with labeled test traffic if real viewers are unavailable.

## Finalization checklist

- Check the exact event restriction on analytics projects. The user reports an explicit ban; the organizer details page could not be retrieved. Research positioning does not establish eligibility if existing functionality falls within that restriction.

- Replace the repository and demo placeholders with verified public links.
- Confirm team membership in the organizer's form.
- Rewrite planned capabilities in the description around what the final build actually demonstrates; remove or explicitly label unfinished features.
- Replace the Google-products section with actual integration details and observed outcomes.
- Distinguish pre-existing AERead infrastructure from work built during the hackathon; check the event's reuse rules before making eligibility claims.
- Verify the link-first flow and current OAuth status. Show actual API reports only if fetched; label any test traffic. Use an actual completed linked-video review before demonstrating it as verified on our own project.
- Explain that views and stated interest are proxies; adoption, task outcomes, economic value and training improvements remain to be validated.
- Obtain separate explicit permission before any future research sharing or training use of private histories and analytics; review consent is not training consent.
- Ensure optional histories and private reports are not public.
- Confirm the current deadline and submission rules in the organizer's interface; publishing a Winner Signal project is not submitting this hackathon entry.
