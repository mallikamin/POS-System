# Chick Shack UK — Meeting Transcript (2026-07-26)

**Source:** `C:\Users\Malik\Videos\rizwan uk meeting.mp4` (699 MB, 13m 39s, recorded 2026-07-26 15:27)
**Transcribed:** faster-whisper `medium` (CPU int8), full pass. The 10:05–11:25 stretch (Urdu/English
code-switching) re-run with `large-v3` — that corrected text is spliced in below and marked.
**Accuracy caveat:** machine transcript, not human-verified. Speaker labels below are **inferred from
context, not from diarisation** — no speaker separation was run. Treat attributions as probable, not certain.

**Speakers (inferred):**
- **CLIENT** — the UK operator (Chick Shack UK). Does most of the talking about requirements.
- **SITARA** — the Sitara Infotech side asking discovery questions and proposing. Says *"I'd be your point
  of contact"* and *"I'll discuss with Fizan as well"*.
- Also referenced on the call: **Fizan/Faizan** and **Rizwan** — SITARA asks at 13:06 whether either has
  questions. See the name ambiguity note in the discovery doc.

---

## Transcript

[00:00] I had to go find a third party POS which I found through EPOS Now. Now that EPOS Now system is
[00:10] okay, it's okay to use, but literally my hands are tied because I can't do anything else with
[00:18] it. The only thing I can do is I can, what do you call it, I can use it for telephone orders
[00:27] or I can use it for takeaway orders, but if I want to integrate a website or do online ordering,
[00:38] I have to do it in their manner, which I don't want to do because their setup is not right for
[00:49] me. So this is why I'm looking to keep, just to clarify, I'm looking to keep the current system I
[00:58] have for the in-house. But if I need, all I'm looking to do at the moment is I'm looking to
[01:06] activate online ordering for the takeaway. So I'm looking for, as I said yesterday, I've got two
[01:15] websites I've got the main website which is just general information and the other website which
[01:21] has got nothing on it right now that's going to be just for online orders so when you order
[01:29] so when you click on that website it'll have the full menu on there
[01:33] and when you order we can accept or reject and then we'll give you a lead time on how long
[01:40] it's going to take to deliver and that's it that's pretty much it that's literally all I'm looking
[01:46] for okay and for the order that will place on website would you take payment in advance or
[01:52] that will be cash on so the customer will have a choice they can pay via the website and
[02:04] the payment will go it will be you need to set up a payment gateway through stripe which
[02:09] I've already made. I've got an account with Stripe and then obviously the transaction
[02:14] payment will go into a designated bank account or the customer can choose to pay on delivery.
[02:25] It will be up to them.
[02:27] Okay and if you're looking to still use your existing EPOS Now system, how are you
[02:34] envisioning that the online ordering would be integrated then?
[02:39] so obviously the online ordering will not be able to be integrated as Fizan's confirmed so we're
[02:48] going to need to have a separate tablet i have got a spare tablet and i've got a spare printer
[02:54] somewhere which i can find and we can probably use that to kind of put it onto that
[03:03] so basically you'd be using two systems simultaneously one is the epos now which
[03:08] which is the regular ordering and how your current workflows are going.
[03:14] Second would be the new system that we'll put in place and we'll integrate it with
[03:19] your website.
[03:20] Am I...
[03:21] Yes.
[03:22] Yeah.
[03:23] Yeah.
[03:24] So like what I'm using right now will be my main system.
[03:28] And then we will have a bit like a Uber Eats tablet or a Justy order pad.
[03:35] Similar to that.
[03:36] Similar to that.
[03:37] are we going to reconcile or basically aggregate both the systems because for
[03:43] example the your EPOS now system shows you your restaurant has done 15,000
[03:49] pounds sales for the day and your second system website is showing the
[03:55] tablet is showing an additional 3,000 pounds so that's 18,000 pounds of
[04:00] sales in a day but your EPOS now has recorded only 15,000 that's fine I'm
[04:06] I'm happy to keep it separate, that's fine. So I'm going to send you on the WhatsApp group,
[04:12] I'm going to send you another website. This is basically my uncle's place, which is
[04:22] not far from where we are. The current system that I'm talking about, the way we're doing,
[04:29] so the way where I'm looking to, because obviously it's not going to integrate with
[04:35] EPOS now. So the way he's doing it, he's doing it in this manner and I'll show you. So this is the
[04:42] website he's got and he's got a separate tablet to his normal, he hasn't even got an EPOS system,
[04:50] he's just got a pen and paper and an EPOS and a normal cash register and he's got a separate
[04:58] tablet where his orders are coming in and he's obviously calculating his sales on pen and paper
[05:06] and then he's calculating his sales on the tablet and then kind of working it out from there.
[05:12] Temporarily we're going to have to do something like this until my contract
[05:15] finishes with EPOS now. And when is your contract finishing with EPOS now?
[05:22] Well, it started in June, so I brought another year left.        <-- "so I've got another year left"
[05:31] So for the next entire year you will be using the ePortsNow system.
[05:35] Yeah, even though I don't like it.
[05:39] I would probably find if the contract has been done, if you have paid something for it, you should use it for the maximum tuition.
[05:46] even I wouldn't advise you to immediately let go of it since it's already in
[05:51] running and you're already your staff is using it so it's better to keep it that
[05:56] way what we'll do is we'll add an additional layer as you said that we
[06:00] you'll get an additional tablet and any basic tablet Android tablets not
[06:07] something to hi-fi on not something too expensive but any basic yeah any
[06:11] basic tablet would do basically the tab all the tablet has to do is to open a
[06:16] link that's it once the link is open you would be able to see live orders
[06:21] flowing in from your website the second thing that we can do whenever that you
[06:26] feel that is aggregating both your accounts so if you're using a separate
[06:31] accounting system let's say QuickBooks or let's say zero or Udo or any
[06:37] your accounting software that you're using for your for EPOS now we what we
[06:42] can do is we can see and we can aggregate both the EPOS now and the POS
[06:47] system that we are going to provide you and then basically give you your
[06:53] accounts and ledgers and profit and loss if you require that on one screen
[06:59] as well so I don't really want to integrate I don't really want I've not
[07:06] integrated EPOS now with any QuickBurgs or any accounting software. I've not done that and I'm
[07:15] not intending to do that either. I want to keep it very basic, very simple with EPOS now because
[07:23] I don't want to give them too much information and I don't want any kind of another app or
[07:29] something to record my sales. So this is what I'm trying to avoid. With regards to this,
[07:36] I would put, my preference would be have like a,
[07:41] like I had, I've just sent another link to the group.
[07:44] So with my previous restaurant I had,
[07:46] I could log in on another link
[07:50] and that was like the backend.
[07:52] It would tell me my daily sales.
[07:54] It will tell me how many orders I had.
[07:58] It would give me my percentages, et cetera.
[08:01] If there's something like that
[08:03] that you can kind of provide,
[08:05] then that would be better for me,
[08:06] rather than trying to integrate it with the ePorts now.
[08:10] I'm happy keeping this separate to ePorts now basically.
[08:13] Then this is something very plug and play
[08:16] and not something with heavy architecture
[08:19] or because you'd be using a separate tablet
[08:21] and keeping everything for the time being separate
[08:25] and independent.
[08:26] So this should be a doable exercise.
[08:31] We'll first configure your website.
[08:33] We'll build the checkout process.
[08:35] I'll look at the reference websites that you've given
[08:38] and build something in the coming week
[08:40] once I have the domain and hosting access.
[08:44] Once the website is up and ready,
[08:46] we'll start the integration with RPOS
[08:49] and then finally hand over to you one single link
[08:52] which you can see at all times,
[08:54] which you can eventually open in your tablet as well,
[08:58] which would be placed either in the kitchen
[09:01] or either at your counter.
[09:03] and we can take it from there.
[09:06] So the domain I have, I've got the domain.
[09:11] We're gonna need to get hosting,
[09:12] but I've got the domain.
[09:16] It's through, I don't know if you know,
[09:18] fast host, but it's through fast host.
[09:21] And I've bought the domain out.
[09:23] And obviously when we need to use it, it's there.
[09:27] The other thing is, obviously your cost thing is,
[09:32] we need to obviously gain an understanding
[09:33] what the costing is involved.
[09:35] And the other thing is,
[09:37] so what I used to do with my previous restaurant was
[09:42] I had a very good system in place
[09:44] where if there was a problem with the website
[09:47] or if there's anything that needed updating,
[09:50] I had a backend team that I could just literally
[09:53] on a WhatsApp, I would just message them and say,
[09:56] could you please change this?
[09:57] Or could you please update that?
[09:59] Is that gonna be the case with you guys?

### --- large-v3 re-transcription (10:05–11:25, Urdu/English code-switching) ---

[10:05] SITARA: ...interacting so far. I'd be your point of contact for now, until the process is ready and
[10:11] everything is up and ready. So any changes you would need, all you have to do is just drop in a text
[10:16] and I'll have a look.
[10:16] CLIENT: Right, okay. The database needs to be good, I guess.
[10:24] SITARA: Database — I didn't get that, please repeat that.
[10:30] CLIENT: [Urdu] In which the orders are saved — we have all the history of the order, at what time
         which order came to us, and everything he has ordered.
[10:39] SITARA: [Urdu] I had sent you a demo link through Fizan. I am not sure if you have reviewed it.
[10:45] Basically, if you review the demo link, it is a front-end view for a demo restaurant.
[10:51] You can play around with it, place orders, you will see all the order history, you will know who
         has ordered — if they have ordered before, on the phone number the old orders will also be retrieved.
[11:05] CLIENT: [Urdu] I saw this front-end yesterday, Faizan sent it to me. That is front-end — on the
         back-end there is a database. **Which database is it?**
[11:13] SITARA: Yeah, so... yeah, so — what kind of costs are involved in this?

> ⚠️ **The client's direct question — "which database is it?" — was never answered.** The conversation
> pivoted straight to costing. Flagged as a follow-up.

### --- back to `medium` pass ---

[11:27] Sir, the costing would be one time cost would be for the website maintenance and website
[11:36] bill and one time cost for the POS implementation at your restaurant, then there would be minimal
[11:45] monthly maintenance fee since I've just gotten clarity of how you're looking
[11:50] for the integration and keeping it separate let me work on the costing and
[11:54] I'll get back to you then yeah because I mean if obviously this is gonna be
[12:01] good to go I have I can put you in touch with three or four other people
[12:06] in the UK who are looking to kind of move away from their current supplier
[12:10] So, basically, one of the links I sent you for Ali Fish and Chips, he's an uncle of mine,
[12:18] and he put me in touch with his contact in the UK to do the website and online ordering
[12:25] from him.
[12:26] It was a local guy from the area, and basically, he's been messing me around.
[12:33] And this is why, when I spoke to Fizan, he goes, we can kind of help you with this.
[12:40] So if obviously the costing and everything is okay, we can then kind of move my uncle
[12:47] over as well and I can give you another two people.
[12:50] That will be great, very kind of you.
[12:53] Let me then just work on this, I'll come up with something and share the commercials
[12:57] with you.
[12:58] And in the meantime, if you have anything else or any further questions from your end,
[13:02] please let me know.
[13:03] No, I think we've covered everything.
[13:06] Is there anything, any other questions that Fizan would like to ask or Rizwan?
[13:10] No, not at all, not right now.
[13:14] From my end, I think we've covered what I needed to cover.
[13:18] Perfect, sounds good.
[13:21] Let me just brainstorm on this, I'll discuss with Fizan as well, then we'll get back
[13:25] to you.
[13:26] Give us a couple of days.
[13:27] No worries.
[13:28] Okay.
[13:29] Very sure.
[13:30] Thank you guys.
[13:31] Thank you for your time.
[13:32] Have a good day.
[13:33] Thank you.
[13:34] Have a good day.
[13:35] Thank you so much.

---

## Links the client said he sent to the WhatsApp group

Not in the video — need to be retrieved from WhatsApp:
1. His **main website** (general info).
2. His **second website** (empty, destined for online ordering).
3. **Ali Fish and Chips** — his uncle's site, cited as the reference model for how this should work.
4. A **backend/reporting link** from his previous restaurant — the admin dashboard he wants replicated.
