# Lecture 1: Introduction
- video_id: cQP8WApzIQQ
- document_id: 18599259b34241d8ac872db3983b3174
- platform: youtube
- duration: 4775s (79m35s)
- chunk_count: 116
- language_guess: en

## L3 brief
This document provides an overview of MIT's 6.824 Distributed Systems introductory lecture, covering foundational course concepts, fault tolerance mechanisms, consistency models, and the MapReduce architecture.

## L2 summary
This document details the introductory lecture for MIT's 6.824 Distributed Systems course taught by Robert Morris. It outlines the core motivations for building distributed systems—including high performance, fault tolerance, and physical distribution—while addressing key technical challenges like concurrency, partial failures, and performance scaling. The text outlines course logistics, required programming labs, and essential abstractions, while exploring fundamental concepts such as replication, consistency models, and non-volatile storage. Finally, it examines Google's MapReduce framework as an illustrative case study, explaining its map and reduce mechanics, master-worker execution, Google File System (GFS) integration, and network bandwidth optimizations.

## Chunks
### chunk 0 [00:01]
Lecture 1: Introduction > Transcript

[00:01] All right.
[00:03] Let's get started.
[00:06] This is 6824 distributed systems.
[00:09] Um
[00:11] So, I'd like to start with just a brief
[00:13] explanation of what I think a
[00:14] distributed system is. Um
[00:18] You know, the core of it is a set of
[00:20] cooperating computers that are
[00:22] communicating with each other over
[00:23] network to um to get some coherent task
[00:26] done. And so, the kinds of examples um
[00:29] that we'll be focusing on in this class
[00:31] are things like storage for big websites
[00:34] or um big data computation such as
[00:37] MapReduce.
[00:39] Um
[00:40] And also somewhat more exotic things
[00:41] like peer-to-peer file sharing. So,
[00:43] these are all just examples of kinds of
[00:45] case studies we'll look at. Um
### chunk 1 [00:45]
Lecture 1: Introduction > Transcript

] these are all just examples of kinds of
[00:45] case studies we'll look at. Um[00:48] And the reason why all this is important
[00:49] is that a lot of critical infrastructure
[00:51] out there is built out of distributed
[00:53] systems.
[00:54] Um the infrastructure that requires more
[00:56] than one computer to get its job done or
[00:58] it sort of inherently needs to be spread
[01:00] out physically.
[01:02] Um
[01:03] So, the reasons why people build this
[01:04] stuff the First of all, before I even
[01:07] talk about distributed systems, just
[01:09] want to remind you that, you know, if
[01:10] you're designing a system or you're
[01:11] designing, you need to solve some
[01:13] problem. If you can possibly solve it on
[01:15] a single computer,
[01:17] you know, without building a distributed
[01:19] system, you should do it that way.
### chunk 2 [01:19]
Lecture 1: Introduction > Transcript

 know, without building a distributed
[01:19] system, you should do it that way.[01:21] Um and and there's many, many jobs you
[01:23] can get done on a single computer. And
[01:24] it's always easier.
[01:27] Um so, distributed systems, you know,
[01:29] you should try everything else before
[01:31] you try building distributed systems cuz
[01:32] they're not they're not simpler.
[01:35] Um so, the reason why people are driven
[01:36] to use lots of cooperating computers are
[01:40] um they need to get high performance.
[01:42] And the way to think about that is they
[01:44] want to get achieve some sort of
[01:46] parallelism.
[01:49] Um lots of CPUs, lots of memories, lots
[01:51] of disk arms moving in parallel.
[01:54] Um
[01:55] Another reason why people build this
[01:57] stuff is to be able to tolerate faults.
[02:06] Have two computers do the exact same
### chunk 3 [02:06]
Lecture 1: Introduction > Transcript

f is to be able to tolerate faults.
[02:06] Have two computers do the exact same[02:08] thing. If one of them fails, you can cut
[02:09] over to the other one.
[02:11] Um another is that some problems are
[02:13] just naturally spread out in space. Like
[02:16] um
[02:17] you know, you want to do interbank
[02:18] transfers of money or something. Well,
[02:20] you know, bank A has this computer in
[02:22] New York City and bank B has this
[02:24] computer in London. You know, you just
[02:26] have to have some way for them to talk
[02:27] to each other and cooperate um in order
[02:29] to carry that out. So, there's some
[02:31] natural sort of physical reasons.
[02:35] So, systems that are inherently
[02:36] physically distributed.
[02:38] And the final reason that people build
[02:40] this stuff is um in order to achieve
### chunk 4 [02:40]
Lecture 1: Introduction > Transcript

 the final reason that people build
[02:40] this stuff is um in order to achieve[02:42] some sort of security goal. So, often by
[02:45] if there's some code you don't trust or
[02:47] you know, you need to interact with
[02:49] somebody, but you know, they may not be
[02:51] they may be malicious or maybe their
[02:53] code has bugs in it. Um so, you don't
[02:55] want to have to trust it. You may want
[02:56] to split up the computation. So, you
[02:58] know,
[02:59] your stuff runs over there on that
[03:00] computer and my stuff runs here on this
[03:02] computer and they only talk to each
[03:03] other through some sort of narrow
[03:05] narrowly defined network protocol.
[03:09] So, I mean, we we may be worried about,
[03:10] you know, security. Um
[03:13] and that's achieved by splitting things
[03:14] up into multiple computers so that they
### chunk 5 [03:14]
Lecture 1: Introduction > Transcript

t's achieved by splitting things
[03:14] up into multiple computers so that they[03:16] can be isolated.
[03:19] The most of this course is going to be
[03:21] about uh performance and fault
[03:23] tolerance, although the other two often
[03:26] work themselves in by way of the sort of
[03:28] constraints on the case studies that
[03:30] we're going to look at.
[03:31] Um
[03:32] you know, all the distributed systems of
[03:34] these problems are um because they have
[03:36] many parts and the parts execute
[03:38] concurrently.
[03:40] Um because they're multiple computers,
[03:42] you get all the problems that come up
[03:43] with concurrent programming. All the
[03:44] sort of complex interactions and weird
[03:46] timing dependent stuff. Um and that's
[03:49] part of what makes distributed systems
[03:51] hard.
[03:52] Another thing that makes distributed
### chunk 6 [03:51]
Lecture 1: Introduction > Transcript

s distributed systems
[03:51] hard.
[03:52] Another thing that makes distributed[03:54] systems hard is that because again you
[03:56] have multiple pieces plus a network you
[03:59] can have
[04:00] very unexpected failure patterns. That
[04:03] is if if you have a single computer it's
[04:05] usually the case that either your
[04:06] computer works or maybe it crashes or
[04:08] suffers a power failure or something.
[04:10] But it pretty much either works or
[04:12] doesn't work. Distributed systems made
[04:14] up of lots of computers you can have
[04:15] partial failures. That is some pieces
[04:18] stop working other people other pieces
[04:20] continue working. Or maybe the computers
[04:22] are working but some part of the network
[04:24] is broken or unreliable.
[04:27] So partial failures is another reason
[04:29] why
[04:31] distributed systems are hard.
### chunk 7 [04:29]
Lecture 1: Introduction > Transcript

ial failures is another reason
[04:29] why
[04:31] distributed systems are hard.[04:33] These are sort of basic challenges.
[04:49] And final reason why it's hard is that
[04:51] you know then the original reason to
[04:52] build a distributed system is often to
[04:54] get
[04:55] higher performance. To get you know a
[04:57] thousand computers worth of performance
[04:59] or a thousand disk arms worth of
[05:01] performance.
[05:03] But it's actually very tricky to obtain
[05:05] that thousand x speed up with a thousand
[05:07] computers.
[05:09] Um
[05:09] often a lot of roadblocks thrown in your
[05:11] way. So the
[05:13] um
[05:19] often takes a bit of careful design to
[05:21] make the system actually give you the
[05:23] performance you feel you deserve.
[05:25] So solving these problems of course can
[05:26] be all about you know addressing these
### chunk 8 [05:26]
Lecture 1: Introduction > Transcript

ving these problems of course can
[05:26] be all about you know addressing these[05:28] issues.
[05:30] Um
[05:31] The reason to take the course is because
[05:33] often the problems and the solutions are
[05:35] quite just technically interesting.
[05:37] Um they're hard problems. For some of
[05:39] these problems there's pretty good
[05:41] solutions known for other problems there
[05:43] not such great solutions known.
[05:45] Um
[05:46] distributed systems are used by a lot of
[05:48] real world um systems out there. Like
[05:51] big websites often involve, you know,
[05:53] vast numbers of computers that are, you
[05:55] know,
[05:56] put together as distributed systems.
[05:59] When I first started teaching this
[06:00] course, um
[06:01] it was distributed systems were
[06:03] something of an academic curiosity. You
### chunk 9 [06:03]
Lecture 1: Introduction > Transcript

 it was distributed systems were
[06:03] something of an academic curiosity. You[06:05] know, people thought, oh, you know, at a
[06:07] small scale they were used sometimes and
[06:09] people felt that oh, someday they'd be
[06:11] might be important. Um,
[06:13] but now particularly driven by the rise
[06:15] of giant websites that have, you know,
[06:18] vast amounts of data and entire
[06:20] warehouses full of computers, um
[06:22] distributed systems in the last 20 years
[06:23] have gotten to be very seriously
[06:26] important part of um
[06:28] computing infrastructure.
[06:31] Um, this means that there's been a lot
[06:33] of attention paid to them, a lot of
[06:34] problems have been solved, but there's
[06:36] still quite a few unsolved problems. So,
[06:38] if you're
[06:39] a graduate student or you're interested
### chunk 10 [06:38]
Lecture 1: Introduction > Transcript

 problems. So,
[06:38] if you're
[06:39] a graduate student or you're interested[06:40] in research, um there's a lot to let a
[06:44] lot of problems yet to be solved in
[06:46] distributed systems that um you could
[06:48] look into as research.
[06:49] And finally, if you like building stuff,
[06:51] this is a good class because it has a
[06:53] lab sequence in which you'll construct
[06:55] some um fairly realistic distributed
[06:58] systems focused on performance and fault
[07:00] tolerance. Um, so you get a lot of
[07:02] practice
[07:03] uh building distri- just
[07:05] building distributed systems and making
[07:07] them work.
[07:09] All right. Let me talk about course
[07:10] structure a bit um
[07:13] before I
[07:15] uh get started on real technical
[07:16] content.
[07:17] Um, you should be able to find the
[07:18] course website using Google.
### chunk 11 [07:17]
Lecture 1: Introduction > Transcript


[07:17] Um, you should be able to find the
[07:18] course website using Google.[07:22] Um, and on the course website is the lab
[07:24] assignments and the
[07:25] course schedule.
[07:26] Um, and also a link to a Piazza
[07:29] page where you can post questions and
[07:31] get answers. Um
[07:33] the course staff, I'm Robert Morris will
[07:35] be giving the lectures. I'll also have
[07:37] four TAs. You guys want to stand up and
[07:40] show your faces.
[07:42] Um
[07:43] the TAs are experts at
[07:46] in particular at doing the solving the
[07:48] labs. They'll be holding office hours.
[07:50] So, if you have questions about the
[07:51] labs, you can come you should go to
[07:53] office hours
[07:54] or you could post questions to Piazza.
[07:57] Um
[07:59] The course has a couple of important
[08:00] components.
[08:03] One is this lectures.
### chunk 12 [08:00]
Lecture 1: Introduction > Transcript

urse has a couple of important
[08:00] components.
[08:03] One is this lectures.[08:07] There's a paper for almost every
[08:09] lecture.
[08:13] There's two exams.
[08:18] There's the labs,
[08:20] programming labs, and
[08:23] there's an optional final project that
[08:25] you can do instead of one of the labs.
[08:35] Um the lectures will be about sort of
[08:37] big ideas in
[08:40] uh distributed systems. There will also
[08:41] be a couple of lectures that are more
[08:43] about sort of lab programming stuff.
[08:46] A lot of the lectures will be taken up
[08:48] by case studies. A lot of the way that I
[08:50] sort of try to bring out the
[08:52] content of distributed systems is by
[08:54] looking at papers, some academic, some
[08:57] written by people in industry describing
[09:01] real solutions to real problems.
[09:04] Um
### chunk 13 [09:01]
Lecture 1: Introduction > Transcript

eople in industry describing
[09:01] real solutions to real problems.
[09:04] Um[09:05] uh these lectures actually be videotaped
[09:08] and I'm hoping to post them online so
[09:10] that you can sort of you're not here
[09:12] or you want to review the lectures.
[09:14] Um you'll be able to look at the
[09:15] videotaped lectures.
[09:18] The papers again there's one to read per
[09:20] week. Um most of them are research
[09:21] papers. Some of them are classic papers
[09:24] like today's paper which I hope some of
[09:26] you have read on MapReduce. It's an old
[09:28] paper, but it was the beginning of it
[09:31] spurred an enormous amount of
[09:32] interesting work
[09:34] both academic and in in real world. So,
[09:35] some are classic and some are more
[09:37] recent papers sort of talking about um
[09:39] more up-to-date research, what people
### chunk 14 [09:39]
Lecture 1: Introduction > Transcript

nt papers sort of talking about um
[09:39] more up-to-date research, what people[09:41] are currently worried about.
[09:43] Um and from the papers I'll be hoping to
[09:45] tease out what the basic problems are,
[09:47] um
[09:48] what ideas people have had that might or
[09:50] might not be useful in solving
[09:51] distributed system problems. Um
[09:54] we'll be looking at sometimes at
[09:55] implementation details in some of these
[09:56] papers um because a lot of this has to
[09:58] do with actual construction of
[10:00] um of software-based systems. Um and
[10:03] we're also going to spend a certain
[10:04] amount of time looking at evaluations.
[10:06] People evaluating how fault-tolerant
[10:07] their systems by measuring them or
[10:09] people measuring how much performance or
[10:11] whether they got performance improvement
[10:13] at all.
[10:14] Um
### chunk 15 [10:11]
Lecture 1: Introduction > Transcript

e or
[10:11] whether they got performance improvement
[10:13] at all.
[10:14] Um[10:16] So, I'm hoping that you'll all read the
[10:18] papers before coming to class. The
[10:20] lectures are
[10:21] um maybe not going to make as much sense
[10:23] if you haven't already read the lecture
[10:25] um cuz there's not enough time to to
[10:27] both explain all the content of the
[10:28] paper and have a sort of interesting
[10:31] reflection on what the paper means
[10:33] online class. So, you really got to read
[10:35] the papers um before coming to class.
[10:37] And hopefully one of the things you'll
[10:38] learn in this class is how to read a
[10:40] paper rapidly and efficiently um and
[10:43] skip over the parts that maybe aren't
[10:45] that important and sort of focus on
[10:47] teasing out um the important ideas.
### chunk 16 [10:47]
Lecture 1: Introduction > Transcript

 that important and sort of focus on
[10:47] teasing out um the important ideas.[10:50] Um on the website there's for every link
[10:53] to by the schedule there's a question um
[10:56] that you should submit an answer for
[10:58] uh for every paper. I think the answers
[11:00] are due at midnight. And we also ask
[11:02] that you submit a question you have
[11:03] about the paper um
[11:06] to the website in order both to give me
[11:08] something to think about as I'm
[11:09] preparing the lecture and if I have time
[11:11] I'll try to answer um at least a few of
[11:13] the questions uh by email.
[11:17] Uh the question and the answer for each
[11:18] paper are due midnight the night before.
[11:21] There's two exams. There's a midterm
[11:24] exam in class I think on the last class
[11:26] meeting before
[11:28] uh
[11:29] spring break.
[11:31] Um and there's a
### chunk 17 [11:26]
Lecture 1: Introduction > Transcript

[11:26] meeting before
[11:28] uh
[11:29] spring break.
[11:31] Um and there's a[11:32] final exam
[11:34] during final exam week at the end of the
[11:36] semester. The exams are going to focus
[11:38] mostly on papers and the labs. Um, and
[11:42] probably the best way to prepare for
[11:44] them as as well as attending lecture and
[11:46] reading the papers. Um,
[11:48] a good way to prepare for the exams is
[11:49] to look at old exams. And we have links
[11:51] to
[11:52] um, 20 years of old exams and solutions.
[11:56] And so, you look at those and sort of
[11:57] get a feel for what kind of questions
[11:59] that I like to ask. And indeed, because
[12:01] we read many of the same papers,
[12:03] inevitably I ask questions each year
[12:05] that
[12:06] um, can't help but resemble questions
[12:09] asked in previous years.
[12:12] The labs, um,
### chunk 18 [12:09]
Lecture 1: Introduction > Transcript

lp but resemble questions
[12:09] asked in previous years.
[12:12] The labs, um,[12:15] there's four programming labs. The first
[12:17] one of them is due
[12:18] uh, Friday next week.
[12:20] Um,
[12:22] they're
[12:24] Lab one is a
[12:28] um,
[12:29] a simple MapReduce lab
[12:31] to implement your own version of the
[12:32] paper that we read today and which I'll
[12:34] be discussing in a few minutes.
[12:36] Um, Lab two
[12:38] uh, involves using a technique called
[12:40] RAFT
[12:42] in order to get fault tol- in order to
[12:44] um,
[12:45] sort of allow, in theory, allow any
[12:47] system to be made fault tolerant by
[12:49] replicating it and having this RAFT
[12:51] technique um, manage the replication and
[12:53] manage sort of automatic cutover if
[12:55] there's a failed if one of the
[12:57] replicated servers fails. So, this is
### chunk 19 [12:57]
Lecture 1: Introduction > Transcript

55] there's a failed if one of the
[12:57] replicated servers fails. So, this is[12:59] RAFT for fault tolerance.
[13:02] Um,
[13:07] in Lab three, you'll use your RAFT
[13:09] implementation in order to build a fault
[13:11] tolerant key-value server.
[13:14] Um,
[13:18] it'll be replicated and fault tolerant.
[13:20] And in Lab four,
[13:22] uh,
[13:23] you'll take your
[13:24] replicated key-value server and clone it
[13:27] into a number of independent groups and
[13:29] you'll split the data um in your key
[13:32] value storage system across all these
[13:34] individual replicated groups to get
[13:36] parallel speed up by running multiple
[13:39] replicated groups in parallel
[13:41] um and you'll also be responsible for
[13:44] uh moving
[13:45] uh
[13:46] the various chunks of data between
[13:49] different servers as they come and go um
### chunk 20 [13:49]
Lecture 1: Introduction > Transcript

 various chunks of data between
[13:49] different servers as they come and go um[13:51] without dropping any balls. So, this is
[13:53] a what's often called a sharded
[13:57] um
[13:59] key value service.
[14:02] And sharding refers to splitting up the
[14:04] data, partitioning the data
[14:06] among multiple servers in order to get
[14:09] uh parallel speed up.
[14:11] Um
[14:13] if you want, instead of doing lab four,
[14:16] um you can do a project of your own
[14:19] choice. And the idea here is if you have
[14:21] some idea for a distributed system, you
[14:23] know, in the style of some of the
[14:25] distributed systems we talked about in
[14:26] the class, if you have your own idea
[14:28] that you want to pursue and you'd like
[14:29] to build something and measure whether
[14:31] it worked in order to explore your idea,
[14:33] um you can do a project. Um
### chunk 21 [14:33]
Lecture 1: Introduction > Transcript

31] it worked in order to explore your idea,
[14:33] um you can do a project. Um[14:36] and so, for a project, you'll pick some
[14:38] teammates cuz we require that uh
[14:40] projects are done in
[14:42] teams of two or three people. Um
[14:46] select some teammates and send your
[14:47] project idea to us and we'll think about
[14:49] it and say yes or no and maybe give you
[14:51] some advice. Um
[14:53] and then if if you go ahead and do if we
[14:54] say yes and you want to do a project,
[14:55] you'd do that in instead of lab four and
[14:57] it's due
[14:58] at the end of the semester and, you
[15:00] know, you'll
[15:01] you should do some
[15:02] uh
[15:03] design work and build a real system and
[15:06] then in the last day of class, you'll
[15:07] demonstrate your system as well as
[15:09] handing in a short uh sort of written
### chunk 22 [15:09]
Lecture 1: Introduction > Transcript

demonstrate your system as well as
[15:09] handing in a short uh sort of written[15:11] report to us about what you built.
[15:14] Um
[15:16] and I posted on the website some
[15:18] some ideas which might or might not be
[15:20] useful for you to sort of spur thoughts
[15:22] about what projects um
[15:24] you might build. But really the the best
[15:26] projects are one where sort of you have
[15:28] a good idea um for the project. And the
[15:31] idea is if you want to do a project, the
[15:34] um you should choose an idea that's sort
[15:35] of in the same vein as the systems that
[15:37] we're um talk about in this class.
[15:41] Um okay, back to labs. Um the lab grades
[15:43] that we give you, uh you hand in your
[15:45] lab code and we run some tests against
[15:47] it and
[15:48] your grade will be based on how many
### chunk 23 [15:47]
Lecture 1: Introduction > Transcript

n some tests against
[15:47] it and
[15:48] your grade will be based on how many[15:49] tests you pass. We give you all the
[15:51] tests that we use, so there's no hidden
[15:52] tests. Um so, if you implement the lab
[15:56] and it reliably passes all the tests,
[15:58] then chances are good um unless there's
[16:00] something funny going on, which there
[16:01] sometimes is, chances are good that if
[16:03] you if your code passes all the tests
[16:05] when you run it, it'll pass all the
[16:06] tests when we run it and you'll get a
[16:07] full score full score. Um so, hopefully
[16:10] there'll be no mystery about what score
[16:12] you're likely to get on the labs.
[16:15] Um
[16:16] let me warn you that
[16:18] uh debugging these labs can be
[16:20] time-consuming um because they're
[16:22] distributed systems and there's a lot of
### chunk 24 [16:22]
Lecture 1: Introduction > Transcript

me-consuming um because they're
[16:22] distributed systems and there's a lot of[16:23] concurrency and communication um
[16:26] sort of strange, difficult to to debug
[16:29] errors can crop up. Um so, you really
[16:33] ought to start the labs early. Don't
[16:35] don't leave them You'll have
[16:37] a lot of trouble if you leave the labs
[16:38] to the last moment. You got to start
[16:40] early. Um if you have problems, please
[16:42] come to the TAs' office hours and please
[16:45] feel free to ask questions about the
[16:47] labs on Piazza. Um and indeed I hope if
[16:50] you know the answer that you'll answer
[16:51] people's questions on Piazza as well.
[16:54] All right.
[16:56] Any questions about the mechanics of the
[16:58] course?
[17:02] Yes.
[17:03] The grade distribution and
[17:05] uh labs
[17:07] and the exams maybe like
### chunk 25 [17:05]
Lecture 1: Introduction > Transcript

:03] The grade distribution and
[17:05] uh labs
[17:07] and the exams maybe like[17:10] The So, the question is what is uh how
[17:12] does how do the different factor these
[17:15] things factor in the grade? I forget,
[17:17] but it's all on the uh it's on the
[17:19] website under something.
[17:23] I think the is the labs are
[17:25] the single most important component.
[17:30] Okay.
[17:34] All right. So, this is a course about
[17:37] about infrastructure for applications.
[17:39] And so, all through this course, there's
[17:41] going to be a sort of split in the way I
[17:42] talk about things between applications
[17:45] which are sort of other people, the
[17:47] customer, somebody else writes, but the
[17:49] applications are going to use the
[17:51] infrastructure that we're thinking about
[17:53] in this course.
### chunk 26 [17:51]
Lecture 1: Introduction > Transcript

use the
[17:51] infrastructure that we're thinking about
[17:53] in this course.[17:54] And so, the kinds of infrastructure that
[17:58] tend to come up a lot
[18:03] are
[18:05] storage,
[18:09] uh communication,
[18:13] and computation.
[18:15] And we'll talk about systems that
[18:17] provide all three of these kinds of
[18:19] infrastructure.
[18:20] The the storage it
[18:23] turns out that storage is going to be
[18:24] the one we focus most on because it's
[18:27] a very well-defined and useful
[18:29] abstraction and
[18:31] usually fairly straightforward
[18:32] abstraction. So, people know a lot about
[18:34] how to build how to use and build
[18:36] storage systems and how to build
[18:40] sort of replicated fault-tolerant
[18:41] high-performance distributed
[18:43] implementations of storage.
[18:45] We'll also talk about some some about
### chunk 27 [18:45]
Lecture 1: Introduction > Transcript

18:43] implementations of storage.
[18:45] We'll also talk about some some about[18:48] computation systems like MapReduce for
[18:49] today is a computation system.
[18:53] And we will talk about communication
[18:55] some,
[18:56] but mostly from the point as a tool that
[18:58] we need to use to build distributed
[18:59] systems. Like computers have to talk to
[19:01] each other over a network, you know,
[19:03] maybe you need reliability or something.
[19:05] And so, we'll talk a bit about
[19:08] we're actually mostly consumers of
[19:10] communication.
[19:11] If you want to learn about communication
[19:13] systems as sort of how they work,
[19:16] um, that's more the topic of 6829.
[19:20] Um,
[19:21] so for storage and computation, um, a
[19:24] lot of our goal is to be able to
[19:26] discover abstractions,
[19:29] um,
### chunk 28 [19:26]
Lecture 1: Introduction > Transcript

:24] lot of our goal is to be able to
[19:26] discover abstractions,
[19:29] um,[19:30] ways of simplifying the interface to
[19:32] these to storage and computation
[19:35] distributed storage and computation
[19:37] infrastructure so that it's easy to
[19:39] build applications on top of it. And
[19:41] what that really means is that we need
[19:43] to we'd like to be able to build
[19:45] abstractions that hide the distributed
[19:47] nature of these,
[19:48] um, of these systems. So, the dream,
[19:52] which is rarely fully achieved, but the
[19:54] dream would be to be able to build an
[19:56] interface that looks to an application
[19:59] as if it's a non-distributed storage
[20:00] system, just like a file system or
[20:02] something that everybody already knows
[20:04] how to program and has a pretty simple
[20:05] model semantics. We'd love to be able to
### chunk 29 [20:05]
Lecture 1: Introduction > Transcript

program and has a pretty simple
[20:05] model semantics. We'd love to be able to[20:08] build interfaces that look and act just
[20:10] like non-distributed, uh, storage and
[20:13] computation systems, um, but are
[20:16] actually,
[20:17] uh,
[20:18] you know, vast, extremely
[20:19] high-performance, fault-tolerant,
[20:21] distributed systems underneath. Um,
[20:24] so we'd love to have abstractions.
[20:30] Um, and you know, as you'll see as the
[20:32] course goes on, we sort of,
[20:36] you know, only part of the way there.
[20:38] It's rare that you find an abstraction
[20:40] for a distributed version of storage or
[20:42] computation that has simple behavior,
[20:45] behaves just like, um,
[20:48] the non-dis- non-distributed version of
[20:50] storage that everybody understands. But,
[20:52] people are getting better at this and,
[20:54] um,
[20:58] uh,
### chunk 30 [20:52]
Lecture 1: Introduction > Transcript

nds. But,
[20:52] people are getting better at this and,
[20:54] um,
[20:58] uh,[20:58] we're we're going to try to study the
[21:00] ways and the what people have learned
[21:01] about building such abstractions.
[21:04] Okay, so,
[21:05] what kind of what kind of,
[21:07] um,
[21:08] topics show up as we're considering
[21:10] these abstractions?
[21:11] Uh
[21:12] the first one that first topic general
[21:14] topic that we'll see a lot
[21:16] and a lot of the systems we look at have
[21:18] to do with implementation.
[21:23] So for example um
[21:25] the kind of tools that you see a lot for
[21:27] for ways people learn how to build these
[21:30] systems are things like remote procedure
[21:31] call whose goal is to mask the fact that
[21:35] we're communicating over an unreliable
[21:37] network.
[21:40] Another
[21:42] uh
[21:42] kind of implementation
### chunk 31 [21:37]
Lecture 1: Introduction > Transcript

iable
[21:37] network.
[21:40] Another
[21:42] uh
[21:42] kind of implementation[21:45] um topic that we'll see a lot is
[21:47] threads.
[21:50] Which are a programming technique that
[21:52] allows us to harness um what allows us
[21:54] to harness multi-core computers, but
[21:56] maybe more important for this class,
[21:58] threads are a way of structuring
[21:59] concurrent operations um in a way that's
[22:02] hopefully simplifies the the programmer
[22:05] view of those concurrent operations. Um
[22:08] and because we're going to use threads a
[22:09] lot it turns out we're going to need to
[22:10] also
[22:12] you know just as it from the
[22:12] implementation level spend a certain
[22:14] amount of time thinking about
[22:15] concurrency control things like locks.
[22:18] Um
[22:23] And the main place that these
### chunk 32 [22:18]
Lecture 1: Introduction > Transcript

ency control things like locks.
[22:18] Um
[22:23] And the main place that these[22:25] implementation ideas will come up in the
[22:26] class that they'll be touched on in many
[22:28] of the papers, but you're going to come
[22:29] face to face with all of this in a big
[22:31] way in the labs. You need to build
[22:33] distributed you know do the programming
[22:34] for distributed system and these are
[22:36] like a lot of the sort of important
[22:39] tools you know beyond the sort of
[22:41] ordinary programming um these are some
[22:43] of the critical tools that you'll need
[22:45] to use um
[22:47] to build distributed systems.
[22:50] Another big topic that
[22:52] um comes up in all the papers we're
[22:54] going to talk about is performance.
[23:02] Um
[23:03] usually the high-level goal of building
[23:05] a distributed system is to get what
### chunk 33 [23:05]
Lecture 1: Introduction > Transcript

ally the high-level goal of building
[23:05] a distributed system is to get what[23:07] people call scalable
[23:10] uh speedup.
[23:12] Um so, we're going to looking for
[23:13] scalability.
[23:17] And what I mean by scalability or
[23:20] scalable speedup is that if I have some
[23:22] problem that I'm solving with one
[23:24] computer and I buy a second computer
[23:28] um to help me execute my problem. If I
[23:31] can now solve the problem in half the
[23:32] time or maybe solve twice as many
[23:35] problem instances,
[23:37] you know, per minute on two computers as
[23:39] I did had on one, then
[23:41] that's an example of scalability. So,
[23:44] sort of two times the, you know,
[23:46] computers or resources
[23:49] um
[23:51] it gets me, you know, two times the
[23:54] performance or throughput.
[24:00] And this is a huge hammer. If you can
### chunk 34 [23:54]
Lecture 1: Introduction > Transcript

[23:54] performance or throughput.
[24:00] And this is a huge hammer. If you can[24:02] build a system that actually has this
[24:03] behavior, namely that
[24:06] if you increase the number of computers
[24:07] you throw at the problem by some factor,
[24:10] you get in that factor more throughput,
[24:12] more performance out of the system.
[24:15] That's a huge win because you can buy
[24:18] computers with just money.
[24:20] Right? Whereas if in order to get the
[24:23] alternative to this um
[24:26] is that in order to get more more
[24:27] performance, you have to pay programmers
[24:29] to restructure your software um to get
[24:32] better performance, to make it more
[24:33] efficient or to apply some sort of
[24:35] specialized techniques, better
[24:37] algorithms or something. Um if you have
[24:39] to pay programmers
[24:41] uh
### chunk 35 [24:39]
Lecture 1: Introduction > Transcript

7] algorithms or something. Um if you have
[24:39] to pay programmers
[24:41] uh[24:42] to fix your code to be faster, that's an
[24:44] expensive way to go. We'd love to be
[24:46] able to just, oh, buy a thousand
[24:47] computers instead of 10 computers and
[24:49] get you know, 100 times more throughput.
[24:51] That's fantastic. And so, this sort of
[24:53] scalability idea is a huge
[24:56] idea in the backs of people's heads when
[24:57] they're like building things like big
[24:59] websites that run on a
[25:00] you know, building full of computers.
[25:02] Um if the building full of computers is
[25:05] there to get a sort of corresponding
[25:07] amount of
[25:08] um performance, but
[25:10] you have to be careful about the design
[25:12] in order to actually get that
[25:13] performance.
[25:15] Um
[25:17] So,
[25:18] uh often the way this looks when we're
### chunk 36 [25:15]
Lecture 1: Introduction > Transcript

rformance.
[25:15] Um
[25:17] So,
[25:18] uh often the way this looks when we're[25:20] looking at diagrams or I'm writing
[25:22] diagrams in this course is that um let's
[25:24] suppose that we're building a website.
[25:26] You know, ordinarily you might have a
[25:27] website that uh
[25:29] um you know, has a HTTP server or let's
[25:32] say it has some has some users
[25:36] um
[25:37] running web browsers
[25:39] and they talk to uh
[25:41] you know, web server running Python or
[25:43] PHP or whatever sort of web server.
[25:48] And the web server talks to some kind of
[25:50] database.
[25:52] Um
[25:55] You know, when you have one or two
[25:56] users, you can just have one computer
[25:58] running both or maybe a computer for the
[26:00] web server and a computer for the
[26:01] database, but maybe all of a sudden you
### chunk 37 [26:01]
Lecture 1: Introduction > Transcript

eb server and a computer for the
[26:01] database, but maybe all of a sudden you[26:03] get really proper popular and you and
[26:05] you uh
[26:06] um you know, 100 million people sign up
[26:08] for your service. Right? How do you
[26:12] you know,
[26:13] how do you fix your certainly can't
[26:14] support a millions of people on a single
[26:16] computer um
[26:18] except by extremely careful
[26:20] labor-intensive optimization
[26:23] um which you don't have time for.
[26:26] So, typically the way you're going to
[26:28] speed things up, the first thing you do
[26:30] is buy more web servers and just split
[26:32] the users so that, you know, half your
[26:34] users or some fraction of the user go to
[26:36] web server one and the other half uh you
[26:38] send them to web server two.
[26:42] And um because, you know, maybe you're
### chunk 38 [26:42]
Lecture 1: Introduction > Transcript

:38] send them to web server two.
[26:42] And um because, you know, maybe you're[26:45] building I don't know what, Reddit or
[26:47] something where all the users need to
[26:48] see the same data ultimately, you have
[26:50] all the web servers talk to the back
[26:52] end. And maybe you can keep on adding
[26:54] web servers for a long time here.
[26:58] Um
[27:01] And so, this is a way of getting
[27:01] parallel speed up on the web server
[27:03] code. You know, if you're running PHP or
[27:04] Python, maybe it's not too efficient. Um
[27:07] as long as each individual web server
[27:09] doesn't put too much load on the
[27:11] database, you can add a lot of web
[27:12] servers
[27:14] um before you run into problems.
[27:16] Um but this kind of scalability
[27:20] is rarely infinite, unfortunately. Um
[27:23] certainly not without serious thought.
### chunk 39 [27:23]
Lecture 1: Introduction > Transcript

arely infinite, unfortunately. Um
[27:23] certainly not without serious thought.[27:24] And so, what tends to happen with these
[27:26] systems is that at some point, after you
[27:28] have 10 or 20 or 100 web servers all
[27:30] talking to the same database,
[27:32] now all of a sudden the database starts
[27:34] to be a bottleneck. And adding more web
[27:35] servers no longer helps. So, it's rare
[27:37] that you get full scalability through
[27:40] sort of infinite numbers of
[27:42] um adding infinite numbers of computers.
[27:45] Some point you run out of gas because
[27:47] the place at which you were adding more
[27:48] computers is no longer the bottleneck.
[27:51] By having lots and lots of web servers,
[27:52] we basically move the bottleneck
[27:54] um the thing that's limiting performance
[27:56] from the web servers to the database.
[27:58] Um
### chunk 40 [27:56]
Lecture 1: Introduction > Transcript

's limiting performance
[27:56] from the web servers to the database.
[27:58] Um[28:01] And at this point, actually, you almost
[28:03] certainly have to do a bit of design
[28:04] work because it's rare that you can take
[28:07] that there's any straightforward way to
[28:09] take a single database and um sort of
[28:12] refactor things with or
[28:15] you can take uh data stored in a single
[28:18] database and refactor it so it's split
[28:20] over multiple databases. Um
[28:24] Uh but it's often a fair amount of work.
[28:26] And
[28:27] um because it's awkward, but people many
[28:29] people actually need to do this. Um
[28:31] we're going to see a lot of examples in
[28:33] this course in which the distributed
[28:34] system people are talking about is a
[28:37] storage system because the authors were
[28:40] running, you know, something like a big
### chunk 41 [28:40]
Lecture 1: Introduction > Transcript

 system because the authors were
[28:40] running, you know, something like a big[28:42] website that ran out of gas on a single
[28:45] database or storage servers. Um
[28:48] Anyway, so the
[28:49] scalability story is we love to build
[28:51] systems that scale this way, but
[28:53] um
[28:54] you know,
[28:57] it's hard to make it or takes work often
[28:59] design work to uh
[29:01] push this idea infinitely far.
[29:04] Um
[29:08] Okay, so
[29:10] um another big topic that comes up a lot
[29:13] is fault tolerance.
[29:23] If you're building a system with a
[29:24] single computer in it, well,
[29:26] a single computer often can stay up for
[29:29] years. Like I have servers in my office
[29:31] that have been up for years without
[29:32] crashing. Um you know, the computer's
[29:35] pretty reliable, the operating system's
### chunk 42 [29:35]
Lecture 1: Introduction > Transcript

ing. Um you know, the computer's
[29:35] pretty reliable, the operating system's[29:37] pretty reliable, apparently the power in
[29:39] my building is pretty reliable. So, it's
[29:40] not uncommon to have single computers
[29:42] that just stay up for amazing amounts of
[29:43] time. However,
[29:46] if you're building systems out of
[29:47] thousands of computers, then even if
[29:50] each computer can be expected to stay up
[29:51] for a year,
[29:53] um with a thousand computers, that means
[29:55] you're going to have like about three
[29:56] computer failures per day
[29:59] in your set of a thousand computers. So,
[30:01] solving big problems with big
[30:03] distributed systems turns sort of very
[30:06] rare fault tolerance, very real failure,
[30:09] very rare failure problems into failure
[30:11] problems that happen just all the time.
### chunk 43 [30:11]
Lecture 1: Introduction > Transcript

re failure problems into failure
[30:11] problems that happen just all the time.[30:14] In a system with a thousand computers,
[30:15] there's almost certainly always
[30:16] something broken. There's always some
[30:18] computer that's either crashed or
[30:21] mysteriously, you know, running
[30:23] incorrectly or slowly or doing the wrong
[30:24] thing. Or maybe there's some piece of
[30:26] the network. Like with a thousand
[30:27] computers, we got a lot of network
[30:29] cables
[30:30] and a lot of network switches. And so,
[30:32] you know, there's always some network
[30:34] cable that somebody stepped on and has
[30:36] unreliability or network cable that fell
[30:38] out or some network switch whose fan is
[30:40] broken and the switch overheated and
[30:41] failed. Like there's always some little
[30:43] problem somewhere in your building sized
### chunk 44 [30:43]
Lecture 1: Introduction > Transcript

Like there's always some little
[30:43] problem somewhere in your building sized[30:47] distributed system.
[30:49] So,
[30:50] big scale turns problems from very rare
[30:52] events you really don't have to worry
[30:54] about that much into just constant
[30:56] problems. That means the failure has to
[30:59] be really or the response, the masking
[31:01] of failures, the ability to proceed
[31:03] without failures just has to be built
[31:05] into the design
[31:06] cuz there's always failures.
[31:09] Um
[31:10] and you know, as part of building, you
[31:12] know, convenient abstractions for
[31:14] application programmers, we really need
[31:16] that to be able to build infrastructure
[31:18] that as much as possible hides the
[31:20] failures from application programmers or
[31:22] masks them or something
[31:24] so that every application programmer
### chunk 45 [31:22]
Lecture 1: Introduction > Transcript

 or
[31:22] masks them or something
[31:24] so that every application programmer[31:26] doesn't have to have a complete
[31:28] complicated story for all the different
[31:30] kinds of failures that can occur.
[31:32] Um
[31:34] there's
[31:36] a bunch of different notions that you
[31:37] can have about um what it means to be
[31:40] fault tolerant. You know, about a little
[31:42] more about, you know, exactly what we
[31:44] mean by that. Um and we'll see a lot of
[31:47] a lot of different flavors, but um among
[31:49] the more common ideas you see, one is
[31:51] availability.
[31:55] Um
[31:57] So, you know, some systems are are
[31:59] designed so that under some kind certain
[32:02] kinds of failures, not all failures, but
[32:04] certain kinds of failures, the system
[32:06] will keep operating
[32:08] um despite the failure while providing
[32:11] um
### chunk 46 [32:08]
Lecture 1: Introduction > Transcript

6] will keep operating
[32:08] um despite the failure while providing
[32:11] um[32:13] you know, undamaged service.
[32:15] Uh the same kind of service it would
[32:16] have provided even if there had been no
[32:18] failure. So, some systems are available
[32:20] in that sense that um up in up a you
[32:23] know, so if you build a replicated
[32:24] service that maybe has two copies,
[32:27] you know, if one of the replicas
[32:29] replica service fail fails, maybe the
[32:31] other server can continue operating. If
[32:34] both fail, Well, you can't
[32:36] you know, you can't promise
[32:38] um
[32:39] availability in that case. So, available
[32:41] systems usually say, "Well,
[32:43] under a certain set of failures, we're
[32:45] going to continue providing service.
[32:46] We're going to be available." If more
[32:48] failures than that occur, um it won't be
### chunk 47 [32:48]
Lecture 1: Introduction > Transcript

going to be available." If more
[32:48] failures than that occur, um it won't be[32:50] available anymore.
[32:53] Another kind of fault tolerance you
[32:55] might um
[32:56] you might have or in addition to
[32:57] availability or by itself is
[32:59] recoverability.
[33:05] And what this means is that if something
[33:07] goes wrong, maybe the service will stop
[33:08] working.
[33:09] That is, it'll simply stop responding to
[33:12] requests, um
[33:14] and it'll wait for someone to come along
[33:16] and repair whatever went wrong, but
[33:17] after the repair occurs, the system will
[33:20] be able to continue as if nothing bad
[33:22] had gone wrong.
[33:23] All right. So, this is a sort of a
[33:24] weaker requirement than availability,
[33:26] cuz here we're, you know, not going to
[33:27] do anything while while the failed until
### chunk 48 [33:27]
Lecture 1: Introduction > Transcript

e we're, you know, not going to
[33:27] do anything while while the failed until[33:30] the failed component has been repaired.
[33:32] But, um the fact that we can get up get
[33:34] going again
[33:36] without, you know, with without any loss
[33:38] of correctness, um is still a
[33:40] significant requirement. It means, you
[33:42] know, recoverable systems typically need
[33:44] to do things like save their latest data
[33:47] on disk or something where they can get
[33:48] it back, you know, after the power comes
[33:50] back up.
[33:52] Um
[33:53] and even among available systems,
[33:55] in order for a system to be useful in
[33:57] real life, um
[34:00] usually what the way available systems
[34:02] are spec'd is that um they're they're
[34:04] available until
[34:06] some number of failures have happened.
[34:07] If too many failures have happened, um
### chunk 49 [34:07]
Lecture 1: Introduction > Transcript

number of failures have happened.
[34:07] If too many failures have happened, um[34:10] an available system will stop working.
[34:13] Or, but you know, will stop responding
[34:14] at all, um but when
[34:18] uh enough things have been repaired,
[34:19] it'll continue operating. So, a good
[34:21] available system will sort of be
[34:23] recoverable as well in the sense that if
[34:24] too many failures occur, um it'll stop
[34:27] answering, but then will continue
[34:28] correctly after that.
[34:31] Um
[34:35] So, this is what we'd love to
[34:37] This is what we'd love to obtain.
[34:40] Um
[34:41] The biggest hammer Well, we'll see a
[34:43] number of approaches to solving these
[34:45] problems. There's really sort of
[34:47] two things that are the most important
[34:49] tools we have in this department. Um one
[34:52] is non-volatile storage. Um so that, you
### chunk 50 [34:52]
Lecture 1: Introduction > Transcript

have in this department. Um one
[34:52] is non-volatile storage. Um so that, you[34:55] know, if something crashes, power fails,
[34:57] or whatever,
[34:58] uh maybe there's a building-wide power
[35:00] failure, um we can use non-volatile
[35:02] storage like hard drives or flash or
[35:04] solid-state drives or something to sort
[35:07] of store a checkpoint or a log
[35:09] um of the
[35:11] uh
[35:12] state of the system. And then when the
[35:13] power comes back up or somebody repairs
[35:16] our power supply, who knows what, we'll
[35:17] be able to read our latest state off the
[35:19] hard drive and um continue from there.
[35:22] So,
[35:23] um so one tool is sort of non-volatile
[35:26] storage.
[35:28] And the management of non-volatile
[35:30] storage is something that comes up a lot
[35:31] because non-volatile storage tends to be
### chunk 51 [35:31]
Lecture 1: Introduction > Transcript

s something that comes up a lot
[35:31] because non-volatile storage tends to be[35:33] expensive to update. And so, a huge
[35:36] amount of the sort of nitty-gritty of
[35:38] building sort of high-performance
[35:41] fault-tolerant systems is in, you know,
[35:43] clever ways to avoid having to write the
[35:46] non-volatile storage too much. In the
[35:48] old days, and even today, um you know,
[35:51] what writing non-volatile storage meant
[35:53] was moving a disk arm and waiting for a
[35:56] disk platter to rotate, right? Both of
[35:59] which are agonizingly slow on the scale
[36:01] of, you know,
[36:03] 3 GHz microprocessors.
[36:06] With things like flash,
[36:07] life's quite a bit better, but still
[36:09] requires a lot of thought to get good
[36:10] performance out of.
[36:12] Um and the other big tool we have for
### chunk 52 [36:10]
Lecture 1: Introduction > Transcript

t good
[36:10] performance out of.
[36:12] Um and the other big tool we have for[36:13] fault tolerance is replication.
[36:18] Um and the management of replicated
[36:20] copies is sort of tricky. You know,
[36:22] that's sort of
[36:24] key problem lurking in any replicated
[36:27] system where we have two servers each
[36:29] with a supposedly identical copy of the
[36:31] system state. Um,
[36:33] the key problem that comes up is always
[36:35] that the two replicas will accidentally
[36:37] drift out of sync and will stop being
[36:39] replicas. Right? And this is just
[36:42] you know, with the back of the every
[36:44] design that we're going to see for using
[36:46] replication to get fault tolerance. Um,
[36:48] and lab two is and lab two are all about
[36:52] management management of replicated
[36:54] copies for fault tolerance.
[36:56] Um,
### chunk 53 [36:54]
Lecture 1: Introduction > Transcript

agement management of replicated
[36:54] copies for fault tolerance.
[36:56] Um,[36:58] as you'll see it's pretty complex.
[37:01] Um,
[37:04] a final topic that
[37:06] final just
[37:07] cross-cutting topic um, is consistency.
[37:15] Um, so, as an example of what I mean by
[37:17] consistency, supposing we're uh building
[37:20] a distributed storage system and it's a
[37:22] key-value service. So, it just supports
[37:25] two operations. Maybe there's a put
[37:26] operation and you give it a key
[37:30] and a value and it the storage system
[37:32] sort of stashes away the value under
[37:35] as the value for this key. So, it
[37:37] maintains it as just a big table of keys
[37:38] and values. And then there's a get
[37:40] operation.
[37:42] You The client sends it a key and
[37:45] the storage service is supposed to
[37:48] you know, respond with a value, the
### chunk 54 [37:48]
Lecture 1: Introduction > Transcript

] the storage service is supposed to
[37:48] you know, respond with a value, the[37:49] value that it stored for that key.
[37:51] Right? And this is kind of a
[37:53] when I can't think of anything else as
[37:54] an example of the distributed system,
[37:56] I'll I'll whip out uh
[37:58] key-value services. Um, and they're very
[38:00] useful, right? They're just sort of the
[38:02] kind of fundamental um,
[38:04] simple version of a storage system.
[38:07] So,
[38:08] of course, if you're an application
[38:10] programmer,
[38:11] it's helpful if these two operations
[38:14] kind of have meanings attached to them,
[38:16] that you can go look in the manual and
[38:18] the manual says, you know, what it what
[38:20] it means, what you'll get back if you
[38:22] call get.
[38:23] Right then sort of what it means for you
[38:25] to call put.
### chunk 55 [38:23]
Lecture 1: Introduction > Transcript

 call get.
[38:23] Right then sort of what it means for you
[38:25] to call put.[38:27] Right so it'd be great if there's some
[38:28] sort of a spec for what they meant
[38:29] otherwise like who knows. How can you
[38:31] possibly write an application without a
[38:33] description of what
[38:34] put and get are supposed to do.
[38:36] Um
[38:37] and this is the topic of consistency.
[38:39] And the reason why it's interesting in
[38:41] distributed systems is that um
[38:44] both for performance and for fault
[38:46] tolerant reasons fault tolerance reason
[38:48] we often have more than one copy of the
[38:50] data floating around.
[38:52] So you know in a non-distributed system
[38:54] where you just have
[38:56] a single server with a single table
[38:59] there's often although
[39:01] not always but there's often like
### chunk 56 [38:59]
Lecture 1: Introduction > Transcript

e table
[38:59] there's often although
[39:01] not always but there's often like[39:03] relatively no ambiguity about what put
[39:05] and get could possibly mean right
[39:07] intuitively you know what put means is
[39:08] update the table and what get means is
[39:10] just get me the version that's stored in
[39:12] the table which um
[39:16] but in a distributed system where
[39:17] there's more than one copy of the data
[39:19] due to replication or caching or
[39:22] um who knows what
[39:23] there may be lots of different
[39:26] versions um
[39:29] of this key value pair floating around.
[39:31] Like if one of the replicas you know if
[39:33] supposing some client issues a put and
[39:36] you know there's two copies of the
[39:40] of the server
[39:41] um
[39:42] so they both have a key value table.
[39:47] Right and maybe key one has value 20 on
### chunk 57 [39:47]
Lecture 1: Introduction > Transcript

hey both have a key value table.
[39:47] Right and maybe key one has value 20 on[39:51] both of them.
[39:54] And then some client issues a put.
[39:56] Right so we have a client over here and
[39:58] it's going to send a put it wants to
[40:00] update the value of one to be 21. Right
[40:03] maybe it's counting stuff in this key
[40:05] value server. So it sends a put
[40:09] with key one
[40:11] and value 21.
[40:13] It sends it to the first server and it's
[40:14] about to send
[40:16] the same put you know it wants to update
[40:18] both copies, right? To keep them in
[40:20] sync. It's about to send this put, but
[40:22] just before it sends the put to the
[40:23] second server, it crashes.
[40:25] All right, power failure, bug in
[40:26] operating system, or something. So, now
[40:28] the state we're left in, sadly, is that
### chunk 58 [40:28]
Lecture 1: Introduction > Transcript

ng system, or something. So, now
[40:28] the state we're left in, sadly, is that[40:30] we sent this put, and so we've updated
[40:34] one of the two replicas to have value
[40:37] 21, but the other one's still with 20.
[40:39] Now, somebody comes along and reads with
[40:40] a get. Now, they might get they want to
[40:43] read the value associated with key one,
[40:45] they might get 21, or get 20, depending
[40:47] on who they talk to. And even if the
[40:49] rule is you always talk to the top
[40:50] server first,
[40:52] if you're building a fault-tolerant
[40:53] system, the actual rule has to be, "Oh,
[40:55] you talk to the top server first, unless
[40:57] it's failed, in which case you talk to
[40:58] the bottom server."
[41:00] Um
[41:01] So, either way, someday you risk
[41:03] exposing this stale copy of the data to
### chunk 59 [41:03]
Lecture 1: Introduction > Transcript

So, either way, someday you risk
[41:03] exposing this stale copy of the data to[41:06] some future get. And it could be that
[41:08] many gets get the updated 21, and then,
[41:10] like next week, all of a sudden, some
[41:12] get yields, you know, a week-old copy of
[41:14] the data.
[41:17] Um so, that's not very consistent.
[41:20] Right? So, um in order but, you know,
[41:22] it's
[41:23] the kind of thing that could happen,
[41:25] right?
[41:26] When we're not careful. So,
[41:28] you know, we need to have we need to
[41:29] actually write down um
[41:32] what the rules are going to be about
[41:33] puts and gets, given this danger of uh
[41:36] due to replication. Um and it turns out
[41:39] there's many different
[41:41] the definitions you can have of
[41:42] consistency.
[41:44] Um
[41:45] you know, many of them are relatively
### chunk 60 [41:42]
Lecture 1: Introduction > Transcript

of
[41:42] consistency.
[41:44] Um
[41:45] you know, many of them are relatively[41:47] straightforward. Many of them sound
[41:48] like, "Well, a get yields the
[41:52] um you know, value put by the most
[41:54] recently completed put."
[41:57] All right? Um
[41:59] And so, that's usually called strong
[42:00] consistency.
[42:02] It turns out also, it's very useful to
[42:05] build systems that have much weaker
[42:06] consistency, that, for example, do not
[42:08] guarantee anything like a get sees the
[42:11] value written by the most recent put.
[42:14] Um
[42:15] and the reason so there's um the
[42:17] strongly consistent systems
[42:22] they usually have some version of get
[42:24] seeing most recent puts. Although you
[42:26] have to there's a lot of details to work
[42:28] out. There's also weekly consistent many
[42:30] sort of
### chunk 61 [42:28]
Lecture 1: Introduction > Transcript

details to work
[42:28] out. There's also weekly consistent many
[42:30] sort of[42:31] flavors of weekly consistent systems
[42:33] that do not make any such guarantee. Um
[42:35] that you know may guarantee well you're
[42:38] you know if someone does a put then you
[42:41] may not see the put. You may see old
[42:42] values that weren't updated by the put
[42:44] for an unbounded amount of time maybe.
[42:47] Um
[42:48] and the reason for people being very
[42:51] interested in weak consistency schemes
[42:53] is that
[42:54] strong consistency that is
[42:56] having reads actually see be guaranteed
[42:59] to see um the most recent write that's a
[43:02] very expensive spec to implement. Um be
[43:06] because what it means is almost
[43:07] certainly that you have to somebody has
[43:09] to do a lot of communication in order to
### chunk 62 [43:09]
Lecture 1: Introduction > Transcript

y that you have to somebody has
[43:09] to do a lot of communication in order to[43:12] actually implement some notion of strong
[43:14] consistency. If you have multiple copies
[43:16] um it means
[43:19] that either the writer or the reader or
[43:21] maybe both has to consult every copy.
[43:23] Like in this case
[43:25] um where you know maybe a client crashed
[43:27] left one updated but not the other. If
[43:29] we wanted to implement strong
[43:31] consistency in the maybe the simple way
[43:33] in this system we'd have readers read
[43:35] both of the copies or if there's more
[43:37] than one copy all the copies
[43:39] and use the most recently written value
[43:40] that they find.
[43:42] Um but that's expensive. That's a lot of
[43:44] chitchat um to read one value.
[43:49] So in order to avoid communication as
[43:51] much as possible um
### chunk 63 [43:49]
Lecture 1: Introduction > Transcript

value.
[43:49] So in order to avoid communication as
[43:51] much as possible um[43:53] particularly if replicas are far away
[43:55] people build weak systems that might
[43:57] actually allow the stale read of an old
[43:59] value in this case. Um
[44:02] although there's often more semantics
[44:05] attached to that to try to make these
[44:06] weak schemes more useful.
[44:08] Um and where this communication problem,
[44:11] you know, strong consistency
[44:14] requiring expensive communication,
[44:16] where this really runs you into trouble
[44:19] is that if we're using replication for
[44:21] fault tolerance, then
[44:23] we really want the replicas to have
[44:25] independent failure probability, to have
[44:27] uncorrelated failure. So, for example,
[44:30] putting both of the replicas of our data
[44:33] in the same rack and in the same machine
### chunk 64 [44:33]
Lecture 1: Introduction > Transcript

oth of the replicas of our data
[44:33] in the same rack and in the same machine[44:36] room is probably a really bad idea
[44:38] because if someone trips over the power
[44:39] cable to that rack, both of our copies
[44:42] of our data are going to die because
[44:44] they're both attached to the same power
[44:46] cable in the same rack. Um
[44:48] so in the search for making
[44:51] replicas as independent in failure as
[44:53] possible in order to get decent fault
[44:55] tolerance,
[44:57] people would love to put different
[44:58] replicas as far apart as possible, like
[45:01] in different cities or maybe on opposite
[45:04] sides of the continent. So, an
[45:05] earthquake that destroys one data center
[45:07] will be extremely unlikely to also
[45:09] destroy
[45:10] um the other data center that is the
[45:12] other copy.
[45:14] Um
### chunk 65 [45:10]
Lecture 1: Introduction > Transcript

troy
[45:10] um the other data center that is the
[45:12] other copy.
[45:14] Um[45:15] you know, so we'd love to be able to do
[45:16] that. If you do that, then the other
[45:18] copy is thousands of miles away um and
[45:22] the rate at which light travels
[45:25] means that it may take on the order of
[45:27] milliseconds or tens of milliseconds to
[45:29] communicate
[45:31] to a data center across the continent in
[45:33] order to update the other copy of the
[45:35] data.
[45:36] And so, that makes this the
[45:37] communication required for strong
[45:39] consistency, for good consistency,
[45:41] potentially extremely expensive. Like
[45:43] every time you want to do one of these
[45:44] put operations or maybe a get, depending
[45:46] on how you implement it, you might have
[45:48] to sit there waiting for like 10 or 20
### chunk 66 [45:48]
Lecture 1: Introduction > Transcript

 you implement it, you might have
[45:48] to sit there waiting for like 10 or 20[45:50] or 30 milliseconds in order to talk to
[45:52] both copies of the data to ensure that
[45:54] they're both updated or or both checked
[45:57] to find the latest copy.
[45:59] Um
[46:00] and
[46:01] that tremendous expense, right? This is
[46:03] 10 or 20 or 30 milliseconds on machines
[46:05] that after all will execute like a
[46:07] billion instructions per second. So,
[46:08] we're wasting a lot of potential
[46:10] instructions while we wait. Um people
[46:13] often on much weaker systems, you're
[46:14] allowed to only update the nearest copy,
[46:16] you're only consult the nearest copy.
[46:18] Now, I mean there's a huge sort of
[46:20] amount of academic and real world uh
[46:23] research on how to how to structure weak
[46:26] consistency guarantees so they're
### chunk 67 [46:26]
Lecture 1: Introduction > Transcript

search on how to how to structure weak
[46:26] consistency guarantees so they're[46:28] actually useful to applications um and
[46:30] how to take advantage of them in order
[46:31] to
[46:32] actually get high performance.
[46:35] All right. So, that's a lightning
[46:38] uh preview of the
[46:40] technical ideas in the course. Um
[46:43] Any questions about this
[46:45] before I start talking about MapReduce?
[46:50] All right. I want to switch to MapReduce
[46:52] um
[46:53] as a sort of detailed case study that's
[46:55] actually going to illustrate um most of
[46:57] the ideas that we've been talking about
[47:00] here.
[47:01] Um
[47:02] MapReduce is a system that was
[47:04] uh
[47:06] uh originally designed and built and
[47:09] used by Google.
[47:11] Um I think the paper dates back to 2004.
[47:15] The problem they were faced with was
### chunk 68 [47:15]
Lecture 1: Introduction > Transcript

think the paper dates back to 2004.
[47:15] The problem they were faced with was[47:17] that they were running huge computations
[47:20] um on terabytes and terabytes of data
[47:22] like creating an index of all of the um
[47:26] content of the web or analyzing the link
[47:29] structure of the entire web in order to
[47:32] um identify the most important pages or
[47:34] the most authoritative pages. As you
[47:36] know, the whole web is well, it's even
[47:38] in those days tens of terabytes of data.
[47:41] Um
[47:43] uh building a index of the web is
[47:45] basically equivalent to a sort
[47:48] running sort of the entire data. Sort,
[47:50] you know, it's like reasonably
[47:52] expensive. Um
[47:53] and to run a sort on the entire content
[47:56] of the web on a single computer, I don't
[47:58] know how long it would have taken, but
### chunk 69 [47:58]
Lecture 1: Introduction > Transcript

web on a single computer, I don't
[47:58] know how long it would have taken, but[47:59] you know, it was weeks or months or
[48:01] years or something. Um so, Google at the
[48:03] time was desperate to be able to run
[48:05] giant computations on giant data on
[48:08] thousands of computers um in order that
[48:10] the the computations could finish
[48:12] rapidly. It was worth it to them to buy
[48:13] lots of computers so that their
[48:15] engineers wouldn't have to spend a lot
[48:17] of time reading the newspaper or
[48:19] something waiting for their uh big
[48:21] compute jobs to finish.
[48:23] Um
[48:25] And so, for a while, they had their
[48:27] clever engineers sort of hand write, you
[48:29] know, if you needed to write a web
[48:30] indexer or some sort of link and out web
[48:32] link analysis tool, you know, Google
### chunk 70 [48:32]
Lecture 1: Introduction > Transcript

er or some sort of link and out web
[48:32] link analysis tool, you know, Google[48:35] bought the computers and they said,
[48:36] "Here, engineers, you know, do write
[48:38] whatever run whatever software you like
[48:39] on these computers." And you know, they
[48:41] would laboriously uh write the sort of
[48:43] one-off manually written software to
[48:46] take whatever problem they were working
[48:47] on and sort of somehow farm it out to a
[48:49] lot of computers and organize that
[48:51] computation and get the data back. Um
[48:56] If you only hire engineers who are
[48:57] skilled distributed systems experts,
[49:01] maybe that's okay, although even then
[49:02] it's
[49:03] probably very wasteful of engineering
[49:05] effort. Um but they wanted to hire
[49:08] people who were skilled at something
[49:09] else.
[49:11] Um
[49:12] and not necessarily uh
### chunk 71 [49:09]
Lecture 1: Introduction > Transcript

ere skilled at something
[49:09] else.
[49:11] Um
[49:12] and not necessarily uh[49:15] engineers who wanted to spend all their
[49:16] time writing distributed systems
[49:18] software. So, they really needed some
[49:20] kind of framework that would make it
[49:21] easy to just have their engineers write
[49:25] the kind of guts of whatever analysis
[49:27] they wanted to do, like sort algorithm
[49:29] or web indexer or link analyzer or
[49:32] whatever, just write the guts of that
[49:33] application and not be able to run it on
[49:35] a thousands of computers um without
[49:38] worrying about the details of how to
[49:40] spread the work over the thousands of
[49:42] computers, how to organize whatever data
[49:45] movement was required, how to cope with
[49:47] the inevitable failures. Um so, they
[49:50] were looking for a framework that would
### chunk 72 [49:50]
Lecture 1: Introduction > Transcript

inevitable failures. Um so, they
[49:50] were looking for a framework that would[49:51] make it easy for non-specialists to be
[49:53] able to write and run giant distributed
[49:57] computations.
[49:59] Um, and so that's what MapReduce is all
[50:01] about.
[50:03] Um,
[50:04] and the idea is that the programmer just
[50:06] write
[50:07] the you know, application designer,
[50:09] consumer of this distributed
[50:11] computation, um, just be able to write a
[50:13] simple map function and a simple reduce
[50:15] function that don't know anything about
[50:18] distribution, um, and the MapReduce
[50:20] framework would take care of everything
[50:22] else.
[50:23] Um,
[50:24] so an abstract view of how
[50:27] um, what MapReduce is up to is it starts
[50:29] by assuming that there's some input and
[50:32] the input is split up into some a whole
### chunk 73 [50:32]
Lecture 1: Introduction > Transcript

ming that there's some input and
[50:32] the input is split up into some a whole[50:35] bunch of different files or chunks in
[50:37] some way. So, we're imagining that um,
[50:40] you know,
[50:41] uh,
[50:42] we have, you know, input file one, input
[50:44] file two,
[50:47] etc.
[50:51] You know, and these inputs are maybe,
[50:52] you know,
[50:53] web pages crawled from the web or more
[50:55] likely sort of big files that contain
[50:58] many web each of which contains many web
[51:00] files
[51:01] crawled from the web.
[51:02] All right. And the way MapReduce starts
[51:05] is that um,
[51:07] you know, you define a map function and
[51:08] the MapReduce framework is going to run
[51:11] uh, your map function
[51:13] on each of
[51:16] uh, the input files.
[51:21] Um, and of course you can see here
[51:22] there's some obvious parallelism
### chunk 74 [51:22]
Lecture 1: Introduction > Transcript

:21] Um, and of course you can see here
[51:22] there's some obvious parallelism[51:24] available. Can run
[51:26] the maps in parallel. So, that each of
[51:28] these map functions only looks at its
[51:29] input and produces output.
[51:31] The output that a map function is
[51:32] required to produce is a list, you know,
[51:35] it
[51:35] takes a file as input, the file is
[51:38] some fraction of the input data, and it
[51:40] produces a list of key-value pairs as
[51:43] output, the map function.
[51:45] Um,
[51:46] and so for example, let's suppose we're
[51:48] writing the simplest possible MapReduce
[51:51] example, a word count MapReduce job,
[51:54] whose whose uh goal is to count the
[51:57] number of occurrences of each word. So,
[51:59] your map function might emit key-value
[52:02] pairs, where the key is the word and the
[52:04] value is just one.
### chunk 75 [52:02]
Lecture 1: Introduction > Transcript

alue
[52:02] pairs, where the key is the word and the
[52:04] value is just one.[52:06] So, for every word it sees, so the this
[52:08] map function will split the input up
[52:10] into words. For every word it sees, it
[52:11] emits that word as the key and one as
[52:14] the value. And then later on, we'll
[52:15] count up all those ones in order to get
[52:18] the final output. So, you know, maybe uh
[52:20] input one has the word um A in it and
[52:24] the word B in it. And so, the output map
[52:27] is going to produce is key A, value one,
[52:30] key B, value one.
[52:32] Maybe the second map invocation um sees
[52:35] a file that has a a B in it and nothing
[52:38] else. So, it's going to implement output
[52:41] B1. Maybe this third input has a A in it
[52:45] and a C in it.
[52:48] All right. So, we run all these maps on
### chunk 76 [52:45]
Lecture 1: Introduction > Transcript

a A in it
[52:45] and a C in it.
[52:48] All right. So, we run all these maps on[52:50] all the input files um and we get this
[52:53] intermediate, what the paper calls
[52:55] intermediate output, which is, for every
[52:57] map,
[52:58] a set of key-value pairs is output.
[53:01] Then the second stage of the computation
[53:03] is to run the reducers.
[53:05] Um and the idea is that the MapReduce
[53:07] framework collects together all
[53:10] instances from all maps of each keyword.
[53:13] So, the MapReduce framework is going to
[53:15] collect together all of the A's,
[53:18] you know, from every map,
[53:20] every key-value pair whose key was A,
[53:22] it's going to take
[53:23] collect them all and hand them to um
[53:30] uh one call of the programmer-defined
[53:33] reduce function. Then it's going to take
[53:36] all the B's and collect them together.
### chunk 77 [53:36]
Lecture 1: Introduction > Transcript

function. Then it's going to take
[53:36] all the B's and collect them together.[53:38] Of course, you know, requires real
[53:39] collection because
[53:41] they were different instances of key B
[53:43] were produced by different
[53:45] invocations of map on different
[53:47] computers. So, we're now talking about
[53:48] data movement.
[53:50] Um so, we're going to collect all the B
[53:51] keys and hand them to a
[53:53] um
[53:55] a different call to reduce that's has
[53:58] all of the B keys
[54:00] as its arguments. And same with C, all
[54:03] the C's.
[54:04] Um
[54:06] So, this going to be the MapReduce
[54:08] framework will arrange for one call to
[54:09] reduce for every key that occurred in um
[54:13] any of the map output.
[54:16] Um
[54:17] and you know, for our sort of silly word
[54:19] count
[54:21] example, all these reducers have to do
### chunk 78 [54:19]
Lecture 1: Introduction > Transcript

 sort of silly word
[54:19] count
[54:21] example, all these reducers have to do[54:23] or any one of them have to do is just
[54:25] count the number of items passed to it.
[54:28] Doesn't even have to look at the items
[54:29] cuz it knows that each of them is the
[54:31] word it's responsible for plus one is
[54:34] the value. You don't have to look at
[54:35] those ones, we'll just count them. Um
[54:37] so, this reducer is going to produce
[54:39] um
[54:40] A and then the count of its inputs. This
[54:44] reduce
[54:45] is going to produce you know, the the
[54:47] key associated with it and then
[54:49] count of its values, which is also two.
[54:56] So, this is what a typical
[54:59] MapReduce job looks like at a high
[55:02] level.
[55:03] Um
[55:05] Just for completeness, the uh
[55:07] Well, some a little bit of terminology.
### chunk 79 [55:07]
Lecture 1: Introduction > Transcript

5] Just for completeness, the uh
[55:07] Well, some a little bit of terminology.[55:09] The whole computation is called a job.
[55:12] Any one um invocation of map or reduce
[55:16] is called a task. So, we have the entire
[55:18] job and it's made up of a bunch of map
[55:20] tasks and then a bunch of reduce tasks.
[55:24] Um
[55:27] So, so an example for this word count,
[55:29] you know, the what the map and reduce
[55:31] functions would look like.
[55:36] Um
[55:40] The map function
[55:43] takes a key and a value as arguments.
[55:45] And And now we're talking about
[55:46] functions like written in an ordinary
[55:48] programming language like C++ or Java or
[55:51] who knows what. Um
[55:54] So, this is just code people ordinary
[55:55] people can write. What What a map
[55:57] function for word count would do is
[55:58] split the the key
### chunk 80 [55:57]
Lecture 1: Introduction > Transcript

What a map
[55:57] function for word count would do is
[55:58] split the the key[56:01] um is the file name, which would
[56:03] typically is ignored when we write code
[56:05] what the file name was. And um the V is
[56:07] the content of this map's input file.
[56:11] So, V is, you know, just contains all
[56:13] this text. Um we're going to split V
[56:16] into words.
[56:21] And then for each word
[56:30] uh we're just going to emit.
[56:33] And emit takes two arguments. Emit's you
[56:35] know, call only map can make. Emit is
[56:37] provided by the MapReduce framework. Um
[56:39] we get to produce we hand emit a a key,
[56:42] which is the word, and a value,
[56:45] um which is
[56:47] string one.
[56:49] So, that's it for the map function. And
[56:51] a word count map function in MapReduce
[56:54] literally could be this simple. Um
### chunk 81 [56:54]
Lecture 1: Introduction > Transcript

 word count map function in MapReduce
[56:54] literally could be this simple. Um[56:57] so, they're sort of promised to make the
[57:00] um and you know, this map function
[57:02] doesn't know anything about distribution
[57:04] or multiple computers or the fact we
[57:06] need may need to move data across the
[57:07] network or who knows what.
[57:09] Right? This is extremely
[57:11] straightforward.
[57:12] Um and the reduce function for
[57:15] uh word count
[57:18] um
[57:19] the reduce is called with you know,
[57:21] remember each reduce is called with sort
[57:22] of all the instances of a given key. Um
[57:25] the MapReduce framework calls reduce
[57:26] with the key that it's responsible for
[57:29] and a vector of all the values that the
[57:33] maps produced Um um
[57:35] associated with that key.
[57:37] Um the key is the word, the values are
### chunk 82 [57:35]
Lecture 1: Introduction > Transcript

[57:35] associated with that key.
[57:37] Um the key is the word, the values are[57:40] all ones, we don't really care about
[57:41] them, we only care about how many there
[57:42] were um
[57:44] and so reduce has its own emit function
[57:47] that uh just takes a a value to be
[57:50] emitted as the final output as the value
[57:52] for the this key. So we're going to emit
[57:55] the length
[57:57] of this array.
[58:00] And so this is also about as simple as
[58:02] reduce functions are in in MapReduce,
[58:05] namely extremely simple.
[58:08] Um and requiring no knowledge about
[58:11] fault tolerance or
[58:13] anything else.
[58:15] All right, any questions about
[58:17] the basic framework? Yes.
[58:18] Is it not necessary that
[58:22] reduce might return something of the
[58:24] same format it received? Like for for
[58:26] instance
### chunk 83 [58:24]
Lecture 1: Introduction > Transcript

 something of the
[58:24] same format it received? Like for for
[58:26] instance[58:28] using the MapReduce paradigm like that,
[58:30] the problem is maybe then we reduce
[58:32] those reductions and we do that step
[58:35] some number of times.
[58:36] You You mean can you feed the output of
[58:39] the reducers sort of
[58:40] could not reduce that
[58:42] again after different sets of
[58:44] Oh, yes.
[58:46] Oh, yes. In in in in in real life, all
[58:49] right, in real life uh it is is routine
[58:53] among MapReduce users to you know,
[58:55] define a MapReduce job that took some
[58:57] inputs and produced some outputs and
[58:59] then have a second MapReduce job, you
[59:01] know, if you're doing some very
[59:02] complicated multi-stage analysis
[59:05] um or iterative algorithm. Like PageRank
[59:09] for example, which is the algorithm
### chunk 84 [59:09]
Lecture 1: Introduction > Transcript

r iterative algorithm. Like PageRank
[59:09] for example, which is the algorithm[59:10] Google uses to sort of
[59:13] um estimate how important or influential
[59:16] different web pages are. That's an
[59:18] iterative algorithm that sort of
[59:20] gradually converges on an answer and if
[59:22] if you implement in MapReduce, which I
[59:24] think they originally did, you have to
[59:25] run the MapReduce job multiple times and
[59:28] the output of each one is sort of, you
[59:30] know, a list of web pages with an
[59:32] updated sort of value or weight or
[59:35] importance for each web page. So, it's
[59:37] routine to take this output and then use
[59:39] it as the input to another MapReduce
[59:41] job.
[59:41] So, you can do
[59:42] that in that MapReduce. I got it. In
[59:44] other words, you're going to send that
[59:46] your reduce is going to
[59:48] get
### chunk 85 [59:46]
Lecture 1: Introduction > Transcript

her words, you're going to send that
[59:46] your reduce is going to
[59:48] get[59:48] all the keys.
[59:50] Well,
[59:53] yeah, you need to sort of set things up
[59:55] the the output of you need to
[59:57] write the reduce function sort of in the
[59:58] knowledge that, oh, I need to produce
[01:00:01] data that's in the format or has the
[01:00:04] information required for the next
[01:00:06] MapReduce job. I mean, this actually
[01:00:08] brings up a little bit of a shortcoming
[01:00:09] in the MapReduce
[01:00:11] framework, which is it's great if you
[01:00:14] are
[01:00:16] if the algorithm you need to run is
[01:00:18] easily expressible as a map followed by
[01:00:20] this sort of
[01:00:22] shuffling of the data by key followed by
[01:00:24] a reduce and that's it. Right, MapReduce
[01:00:27] is fantastic for algorithms that can be
### chunk 86 [01:00:27]
Lecture 1: Introduction > Transcript

d that's it. Right, MapReduce
[01:00:27] is fantastic for algorithms that can be[01:00:28] cast in that form. And furthermore, each
[01:00:31] of the maps has to be completely
[01:00:32] independent. The maps are required to be
[01:00:36] uh
[01:00:38] functional, pure functional
[01:00:41] functions that just look at their
[01:00:43] arguments and nothing else. And it's,
[01:00:45] you know, it's like it's a restriction.
[01:00:46] Um and it turns out that many people
[01:00:48] want to run much longer pipelines that
[01:00:49] involve lots and lots of different kinds
[01:00:51] of processing. And with MapReduce, you
[01:00:53] have to sort of cobble that together
[01:00:54] from multiple
[01:00:56] MapReduce
[01:00:57] you know, distinct MapReduce jobs. And
[01:00:59] more advanced systems, which we'll talk
[01:01:01] about later in the course, are much
### chunk 87 [01:01:01]
Lecture 1: Introduction > Transcript

dvanced systems, which we'll talk
[01:01:01] about later in the course, are much[01:01:02] better at allowing you to specify the
[01:01:05] complete pipeline of computations and
[01:01:07] they'll do optimization.
[01:01:09] You know, the framework realizes all the
[01:01:10] stuff you have to do and organize much
[01:01:12] more complicated efficiently optimize
[01:01:15] much more complicated computations.
[01:01:18] Do you have a question?
[01:01:19] Okay. So, in the paper, they distinguish
[01:01:21] between mappers and map functions,
[01:01:23] reducers and reduce functions.
[01:01:26] Uh I guess that's just like the
[01:01:27] processes that are running the map
[01:01:29] functions.
[01:01:30] What are the
[01:01:31] things that you would consider more
[01:01:33] important to distinguish between
[01:01:35] like the processes that are running
### chunk 88 [01:01:35]
Lecture 1: Introduction > Transcript

 important to distinguish between
[01:01:35] like the processes that are running[01:01:36] these functions?
[01:01:39] Um from the programmer's point of view,
[01:01:41] it's just about map and reduce. From our
[01:01:43] point of view, it's going to be about
[01:01:45] the worker processes and the worker
[01:01:48] servers
[01:01:50] that
[01:01:51] that are they're part of the MapReduce
[01:01:53] framework that, among many other things,
[01:01:55] call the map and reduce functions.
[01:01:58] So,
[01:01:59] um
[01:02:00] Yeah, from our point of view, we care a
[01:02:02] lot about how this is organized by the
[01:02:04] surrounding framework. This is sort of
[01:02:06] the programmer's view with all the
[01:02:08] distributed stuff stripped out.
[01:02:10] Um
[01:02:12] Yes.
[01:02:16] Sorry, I got to
[01:02:21] Say it again.
### chunk 89 [01:02:12]
Lecture 1: Introduction > Transcript

01:02:10] Um
[01:02:12] Yes.
[01:02:16] Sorry, I got to
[01:02:21] Say it again.[01:02:22] Sorry, do you emit locally or
[01:02:24] Oh, you mean where does the emit get
[01:02:25] data go?
[01:02:26] And also, where does the reduce function
[01:02:28] where does it run? Like external or
[01:02:31] Okay, so there's two questions. One is
[01:02:35] when you call emit, what happens to
[01:02:37] data? And the other is where are the
[01:02:39] functions run? So, um
[01:02:43] um
[01:02:47] The the actual answer is that uh first,
[01:02:50] where does the stuff run? There there's
[01:02:52] a number of say a thousand servers. Um
[01:02:55] actually, the right thing to look at
[01:02:57] here is figure one in the paper. Um
[01:03:00] The sitting underneath this in the real
[01:03:02] world, there's some big collection of
[01:03:04] servers.
[01:03:06] And
[01:03:07] um
### chunk 90 [01:03:04]
Lecture 1: Introduction > Transcript

 there's some big collection of
[01:03:04] servers.
[01:03:06] And
[01:03:07] um[01:03:08] we'll call them maybe worker servers or
[01:03:09] workers. And um there's a also a a
[01:03:13] single master server that's organizing
[01:03:15] the whole computation. And what's going
[01:03:17] on here is the master server for no
[01:03:20] knows that there's some number of input
[01:03:23] files, you know, 5,000 input files. And
[01:03:26] it farms out invocations of map to the
[01:03:29] different workers. So, it'll send a
[01:03:30] message to worker seven saying, "Please
[01:03:32] run, you know,
[01:03:35] this map function on such and such an
[01:03:37] input file."
[01:03:39] Um and then the worker function, which
[01:03:41] is, you know, part of MapReduce and
[01:03:44] knows all about MapReduce, will then,
[01:03:46] um
### chunk 91 [01:03:44]
Lecture 1: Introduction > Transcript

 of MapReduce and
[01:03:44] knows all about MapReduce, will then,
[01:03:46] um[01:03:47] read the file, read the input, whatever
[01:03:50] whichever input file,
[01:03:52] um
[01:03:52] and call this map function with the file
[01:03:55] name value as its arguments.
[01:03:57] Then that worker process will
[01:04:01] implement what implements emit. And
[01:04:03] every time the map calls emit, uh the
[01:04:05] worker process
[01:04:07] will write this data um to files on the
[01:04:10] local disk. So, what happens to map
[01:04:13] emits?
[01:04:14] Th- and is they produce files on the map
[01:04:17] workers local disk that are accumulating
[01:04:21] all the keys and values produced by the
[01:04:23] maps run on that worker.
[01:04:26] Um
[01:04:27] So, at the end of the map phase,
[01:04:29] um what we're left with is all those
### chunk 92 [01:04:29]
Lecture 1: Introduction > Transcript

So, at the end of the map phase,
[01:04:29] um what we're left with is all those[01:04:31] worker machines, each of which has the
[01:04:34] output of some of whatever maps were run
[01:04:37] on that worker machine.
[01:04:40] Then the MapReduce
[01:04:42] workers arrange to move the data to
[01:04:45] where it's going to be needed for the
[01:04:46] reducers. So, and since
[01:04:49] in a you know, in a typical big
[01:04:51] computation,
[01:04:52] you know, this this reduce invocation is
[01:04:54] going to need
[01:04:56] all map output that
[01:04:59] um
[01:04:59] mentioned the key A. But, it's going to
[01:05:01] turn out, you know, this is a
[01:05:03] sort of simple example, but probably
[01:05:07] in general, every single map invocation
[01:05:09] will produce lots of keys including some
[01:05:12] instances of key A. So, typically, in
### chunk 93 [01:05:12]
Lecture 1: Introduction > Transcript

uce lots of keys including some
[01:05:12] instances of key A. So, typically, in[01:05:14] order before we can even run this reduce
[01:05:16] function, the MapReduce framework, that
[01:05:18] is the
[01:05:19] MapReduce worker running on one of our
[01:05:21] thousand servers, is going to have to go
[01:05:23] talk to every single other of the
[01:05:25] thousand servers and say, "Look,
[01:05:27] you know, I'm going to run the reduce
[01:05:28] for key A. Please, look at the
[01:05:31] intermediate map output stored on your
[01:05:33] disk and fish out all of the instances
[01:05:36] of key A and send them over the network
[01:05:38] to me."
[01:05:40] So, the reduce worker is going to do
[01:05:41] that. It's going to fetch
[01:05:43] from every worker all of the instances
[01:05:45] of a key that it's responsible for, that
### chunk 94 [01:05:45]
Lecture 1: Introduction > Transcript

 worker all of the instances
[01:05:45] of a key that it's responsible for, that[01:05:47] the master has told it to be responsible
[01:05:50] for. And once it's collected all of that
[01:05:51] data, then it can call reduce.
[01:05:54] And the reduce
[01:05:56] function itself calls reduce emit, which
[01:05:58] is different from the map emit. And
[01:06:01] what reduce emit does is writes the
[01:06:04] output to
[01:06:06] a file
[01:06:09] in a cluster file service that Google
[01:06:12] uses.
[01:06:13] So, here's something I haven't
[01:06:14] mentioned. Um
[01:06:17] I haven't mentioned where the input
[01:06:18] lives
[01:06:20] and where the output lives. They're both
[01:06:22] files. Um
[01:06:25] because any piece of input
[01:06:27] we want the flexibility to be able to
[01:06:30] read any piece of input on any worker
[01:06:32] server,
### chunk 95 [01:06:30]
Lecture 1: Introduction > Transcript

o be able to
[01:06:30] read any piece of input on any worker
[01:06:32] server,[01:06:34] that means we need some kind of network
[01:06:35] file system
[01:06:37] to store the input data.
[01:06:40] Um
[01:06:41] and so, indeed, the paper talks about
[01:06:43] this thing called GFS for
[01:06:46] Google file system.
[01:06:48] Um and GFS is a cluster file system. And
[01:06:51] GFS actually runs on exactly the same
[01:06:53] set of workers that worker servers that
[01:06:56] run MapReduce.
[01:06:58] And the input GFS just automatically,
[01:07:00] when you, you know, it's a file system,
[01:07:02] you can read and write files, it just
[01:07:03] automatically splits up any big file you
[01:07:06] store on it across lots of servers in 64
[01:07:09] megabyte chunks.
[01:07:11] So, if you write, you know, if you have
[01:07:12] 10 TB of crawled web page contents,
### chunk 96 [01:07:12]
Lecture 1: Introduction > Transcript

 you write, you know, if you have
[01:07:12] 10 TB of crawled web page contents,[01:07:17] and you just write them to GFS, even as
[01:07:19] a single big file, GFS will
[01:07:21] automatically split that vast amount of
[01:07:23] data up into 64 kilobyte chunks
[01:07:25] distributed evenly over all of the GFS
[01:07:28] servers, which is to say
[01:07:30] all the servers that Google has
[01:07:31] available. And that's fantastic. That's
[01:07:34] just what we need.
[01:07:35] If we then want to run a MapReduce job
[01:07:37] that takes the entire crawled web as
[01:07:39] input,
[01:07:40] the data's already stored in a way
[01:07:42] that's split up evenly across all the
[01:07:44] servers. And so, that means that um
[01:07:47] the map workers, you know, we're going
[01:07:48] to launch you know, if we have a
[01:07:50] thousand servers, we're going to launch
### chunk 97 [01:07:50]
Lecture 1: Introduction > Transcript

launch you know, if we have a
[01:07:50] thousand servers, we're going to launch[01:07:51] a thousand map workers, each reading
[01:07:53] 1/1000 of the input data, and they're
[01:07:56] going to be able to read the data in
[01:07:57] parallel
[01:07:59] um from a thousand GFS file servers,
[01:08:02] thus getting, you know, tremendous total
[01:08:05] read throughput, you know, the read
[01:08:07] throughput of a thousand servers.
[01:08:09] Yeah.
[01:08:11] And they're not necessarily the same
[01:08:12] servers that would
[01:08:13] be running the map tasks.
[01:08:16] The ones that are storing the
[01:08:18] the input data for GFS on GFS.
[01:08:21] So, so are you thinking maybe that
[01:08:23] Google has one set of physical machines
[01:08:25] that run GFS and a separate set of
[01:08:27] physical machines that run MapReduce
[01:08:30] jobs?
### chunk 98 [01:08:27]
Lecture 1: Introduction > Transcript

separate set of
[01:08:27] physical machines that run MapReduce
[01:08:30] jobs?[01:08:30] I was just saying that the
[01:08:33] the
[01:08:34] map workers like might have to read from
[01:08:36] a different machine.
[01:08:38] Okay.
[01:08:38] They're not necessarily on the same ones
[01:08:40] on the
[01:08:41] Right. So, the question is
[01:08:44] what does this arrow here actually
[01:08:46] involve? Um
[01:08:48] and the answer to that actually it sort
[01:08:49] of changed over the years as Google's
[01:08:52] evolved the system, but
[01:08:54] um you know, what what this
[01:08:56] in the most general case, if we have big
[01:08:58] files stored in some big network file
[01:09:01] system like, you know, it's GFS is a bit
[01:09:03] like AFS you might have used on Athena.
[01:09:06] Where you go talk to some collection and
### chunk 99 [01:09:06]
Lecture 1: Introduction > Transcript

u might have used on Athena.
[01:09:06] Where you go talk to some collection and[01:09:08] your data split over big collection of
[01:09:10] servers, you have to go talk to those
[01:09:11] servers over the network to retrieve
[01:09:12] your data. Um in that case, what this
[01:09:14] arrow might represent is
[01:09:17] the map the MapReduce worker process has
[01:09:20] to go off and talk across the network to
[01:09:22] the correct GFS server or maybe servers
[01:09:25] that store its part of the input and
[01:09:28] fetch it over the network to the
[01:09:30] MapReduce worker machine in order to
[01:09:32] pass the map. And that that's certainly
[01:09:34] the most general case.
[01:09:36] Um and that was eventually how MapReduce
[01:09:38] actually worked.
[01:09:40] In the world of this paper though,
[01:09:43] um and and if you did that, that's a lot
### chunk 100 [01:09:43]
Lecture 1: Introduction > Transcript

 world of this paper though,
[01:09:43] um and and if you did that, that's a lot[01:09:45] of network communication.
[01:09:47] Right, you're talking about 10 terabytes
[01:09:48] of data and then we have to move 10
[01:09:49] terabytes across their data center
[01:09:51] network, which
[01:09:53] you know,
[01:09:53] data center networks run at gigabits per
[01:09:55] second, but it's still a lot of time to
[01:09:56] move tens of terabytes of data.
[01:10:01] In order to try to and indeed in the
[01:10:03] world of this paper in 2004, the most
[01:10:05] constraining bottleneck in their
[01:10:07] MapReduce system was network throughput.
[01:10:10] Um because they were running on a
[01:10:11] network, if you sort of read as far as
[01:10:13] the
[01:10:15] evaluation section,
[01:10:16] their network
[01:10:18] um their network is was uh
[01:10:22] um
### chunk 101 [01:10:16]
Lecture 1: Introduction > Transcript

on,
[01:10:16] their network
[01:10:18] um their network is was uh
[01:10:22] um[01:10:23] you know, they had thousands of
[01:10:24] machines.
[01:10:27] Uh
[01:10:28] whatever um
[01:10:29] and they would collect machines, they
[01:10:31] would plug machines into you know, each
[01:10:33] rack of machines into you know, an
[01:10:35] Ethernet switch for that rack or
[01:10:36] something. But then, you know, they all
[01:10:38] need to talk to each other.
[01:10:39] And but there was a root Ethernet switch
[01:10:43] that all of the rack Ethernet switches
[01:10:44] talked to. And this and you know, so if
[01:10:47] you just pick
[01:10:49] some MapReduce worker and some GFS
[01:10:51] server, you know, chances are these half
[01:10:53] the time the communication between them
[01:10:55] has to pass through this one root
[01:10:56] switch. The root switch had
### chunk 102 [01:10:56]
Lecture 1: Introduction > Transcript

:10:55] has to pass through this one root
[01:10:56] switch. The root switch had[01:10:59] um only some amount of total throughput,
[01:11:01] which I forget. Uh, you know,
[01:11:05] some number of gigabits per second.
[01:11:07] Um,
[01:11:09] anyway, forget the number. Well,
[01:11:11] but when I did the division, um,
[01:11:14] that is divided up the
[01:11:17] total throughput available in the root
[01:11:18] switch by the roughly 2,000 servers that
[01:11:21] they used in the paper's experiments,
[01:11:23] what I got was that each machine's share
[01:11:25] of the root switch or of the total
[01:11:27] network capacity was only 50 megabits
[01:11:30] per second per second
[01:11:32] um, in their setup.
[01:11:35] So, 50 megabits per second per machine.
[01:11:40] Um, and that might seem like a lot, 50
[01:11:42] megabits, gosh, millions and millions,
### chunk 103 [01:11:42]
Lecture 1: Introduction > Transcript

that might seem like a lot, 50
[01:11:42] megabits, gosh, millions and millions,[01:11:44] um, but it's actually quite small
[01:11:46] compared to how fast the disks run or
[01:11:49] uh, CPUs run. And so, this with their
[01:11:52] network, this 50 megabits per second was
[01:11:54] like a tremendous limit. And so, they
[01:11:56] really stood on their heads in the
[01:11:57] design described in the paper to avoid
[01:12:00] using the network.
[01:12:01] Um, and they played a bunch of tricks to
[01:12:03] avoid sending,
[01:12:05] um, stuff over the network when they
[01:12:06] possibly could avoid it. One of them
[01:12:08] was,
[01:12:09] um, they would they ran the GFS servers
[01:12:14] and the MapReduce workers on the same
[01:12:16] set of machines. So, they have 1,000
[01:12:18] machines,
[01:12:20] they'd
[01:12:21] run GFS, they'd implement their GFS
### chunk 104 [01:12:20]
Lecture 1: Introduction > Transcript

2:18] machines,
[01:12:20] they'd
[01:12:21] run GFS, they'd implement their GFS[01:12:23] service on that 1,000 machines and run
[01:12:26] MapReduce on the same 1,000 machines.
[01:12:29] And then when the master was splitting
[01:12:31] up the map work, um, and sort of farming
[01:12:34] it out to different workers, it would
[01:12:35] cleverly,
[01:12:37] when it was, um,
[01:12:39] about to run the map that was going to
[01:12:41] read from input file one, it would
[01:12:44] figure out from GFS which server
[01:12:46] actually holds input file one on its
[01:12:48] local disk. And it would send the map
[01:12:52] for that input file to to the MapReduce
[01:12:54] software on the same machine. So that by
[01:12:57] default, this arrow was actually local
[01:13:00] local read from the local disk and did
[01:13:02] not involve the network. And you know,
### chunk 105 [01:13:02]
Lecture 1: Introduction > Transcript

ad from the local disk and did
[01:13:02] not involve the network. And you know,[01:13:04] depending on failures or load or
[01:13:06] whatever, that it couldn't always do
[01:13:08] that. But almost all of the maps would
[01:13:11] be run in the very same machine that
[01:13:12] stored the data, thus saving them
[01:13:14] um
[01:13:15] vast amount of time that they would
[01:13:17] otherwise had to wait to move the input
[01:13:19] data across the network. Um
[01:13:22] The next trick they played is that
[01:13:25] uh map, as I mentioned before, stores
[01:13:26] its output on the local disk of the
[01:13:28] machine that you run the map on. So
[01:13:30] again, storing the output of the map
[01:13:32] does not require network communication,
[01:13:34] at least not immediately, um because the
[01:13:36] output's stored on the disk.
[01:13:38] However,
### chunk 106 [01:13:36]
Lecture 1: Introduction > Transcript

tely, um because the
[01:13:36] output's stored on the disk.
[01:13:38] However,[01:13:40] we know for sure that one way or
[01:13:42] another, in order to group together all
[01:13:45] of you know, by the way the MapReduce is
[01:13:46] defined,
[01:13:48] in order to group together all of the
[01:13:50] values associated with a given key and
[01:13:52] pass them to a single um invocation of
[01:13:55] reduce on some machine, this is going to
[01:13:57] require network communication. We're
[01:13:59] going to you know, we want to need to
[01:14:01] fetch all the A's and give them a single
[01:14:03] machine, they have to be moved across
[01:14:05] the network.
[01:14:07] And so this shuffle, this movement of
[01:14:09] the keys from it's kind of um you know,
[01:14:12] originally stored by row in the on the
[01:14:14] same machine that ran the map, we need
### chunk 107 [01:14:14]
Lecture 1: Introduction > Transcript

ly stored by row in the on the
[01:14:14] same machine that ran the map, we need[01:14:16] them essentially to be stored on by
[01:14:18] column on the machine that's going to be
[01:14:19] responsible for reduce. Um this
[01:14:22] transformation of row storage to
[01:14:23] essentially column storage is called the
[01:14:25] paper calls it shuffle. Um and it really
[01:14:28] that required moving every piece of data
[01:14:30] across the network from the map that
[01:14:32] produced it to the reduce that would
[01:14:34] need it. And that was like the expensive
[01:14:36] part of the um of the MapReduce. Yeah.
[01:14:40] Why didn't they
[01:14:41] make the reduce something that would run
[01:14:43] sort of like you would have you you
[01:14:44] would keep your output as you have it
[01:14:46] already and you just take one at a time,
### chunk 108 [01:14:46]
Lecture 1: Introduction > Transcript

p your output as you have it
[01:14:46] already and you just take one at a time,[01:14:48] and then you wouldn't have to wait until
[01:14:50] all the maps are done.
[01:14:51] Yeah,
[01:14:52] you're right. You you you could imagine
[01:14:53] a different definition in which you have
[01:14:54] a more kind of streaming reduce. Um I I
[01:14:57] don't know
[01:14:58] I haven't thought this through. I I
[01:14:59] don't know why whether that would be
[01:15:01] feasible or not. Um certainly as far as
[01:15:03] programmer interface, like if the goal
[01:15:05] their number one goal really was
[01:15:09] to be able to make it easy to program by
[01:15:11] people who just had no idea what was
[01:15:13] going on in the system. So, it may be
[01:15:15] that you know, this spec this is really
[01:15:17] the way reduce functions look um in you
### chunk 109 [01:15:17]
Lecture 1: Introduction > Transcript

now, this spec this is really
[01:15:17] the way reduce functions look um in you[01:15:21] know, in C++ or something. Like a
[01:15:23] streaming version of this is now
[01:15:25] starting to look
[01:15:27] I don't know how it would look.
[01:15:29] Probably not this simple. Um
[01:15:31] but you know,
[01:15:32] maybe it could be done that way. And
[01:15:33] indeed, many modern systems
[01:15:36] and people have gotten a lot more
[01:15:38] sophisticated
[01:15:39] um with modern things that are the
[01:15:41] successors to MapReduce, and they do
[01:15:43] indeed involve processing streams of
[01:15:46] data often rather than this very batch
[01:15:49] approach. That is a batch approach in
[01:15:51] the sense that we wait until we get all
[01:15:53] the data, and then we process it. Um so,
[01:15:55] first of all, that you then have to have
### chunk 110 [01:15:55]
Lecture 1: Introduction > Transcript

d then we process it. Um so,
[01:15:55] first of all, that you then have to have[01:15:57] a notion of finite inputs, right? Um and
[01:16:00] modern systems often do indeed use
[01:16:02] streams, and
[01:16:04] and are able to take advantage of some
[01:16:06] efficiencies due to that.
[01:16:08] Um but not MapReduce.
[01:16:11] Um
[01:16:13] Okay, so uh
[01:16:14] this is the point at which the shuffle
[01:16:16] is where all the network uh traffic
[01:16:18] happens. This can actually be a vast
[01:16:20] amount of data. So, if you think about
[01:16:21] sort,
[01:16:22] um if you're sorting, the um the output
[01:16:25] of the sort has the same size as the
[01:16:27] input to the sort. So, that means that
[01:16:30] if you're you know, if your input is 10
[01:16:31] TB of data, and you're running a sort,
[01:16:34] you're moving 10 TB of data across the
### chunk 111 [01:16:34]
Lecture 1: Introduction > Transcript

ta, and you're running a sort,
[01:16:34] you're moving 10 TB of data across the[01:16:35] network at this point. Um and your
[01:16:37] output will also be 10 TB. And so, this
[01:16:39] is quite a lot of data. And then indeed,
[01:16:41] it is for many MapReduce jobs. Although,
[01:16:43] not all. There's some that say
[01:16:44] significantly reduce the amount of data
[01:16:47] at these stages.
[01:16:48] Um
[01:16:49] somebody mentioned, "Oh, what if you
[01:16:50] want to feed the output of reduce into
[01:16:52] another MapReduce job?" And indeed, that
[01:16:54] was often what people wanted to do. And
[01:16:56] in any case, the output of the reduce
[01:16:58] might be enormous, like for sort or web
[01:17:00] indexing. The output of the reduce is uh
[01:17:02] on 10 TB of input, the output of the
[01:17:05] reduce is again going to be 10 TB. So,
### chunk 112 [01:17:05]
Lecture 1: Introduction > Transcript

TB of input, the output of the
[01:17:05] reduce is again going to be 10 TB. So,[01:17:07] the output of the reduce was also stored
[01:17:09] on GFS. Um and the system would, you
[01:17:12] know, reduce would just produce these
[01:17:13] key-value pairs, but the um
[01:17:17] MapReduce framework would gather them up
[01:17:19] and write them into giant files on GFS.
[01:17:22] Um and so, there was another
[01:17:25] uh
[01:17:25] round of network communication required
[01:17:28] to um get the output of each reduce to
[01:17:31] the GFS server that needed to store that
[01:17:33] reduce. And because you might think that
[01:17:35] they could have um
[01:17:37] played the same trick with the output of
[01:17:39] storing the output on the GFS server
[01:17:42] that happened to run um
[01:17:45] the MapReduce worker that ran the
### chunk 113 [01:17:42]
Lecture 1: Introduction > Transcript


[01:17:42] that happened to run um
[01:17:45] the MapReduce worker that ran the[01:17:46] reduce. Um and maybe they did do that,
[01:17:49] but because GFS as well as splitting
[01:17:52] data up for performance, also keeps two
[01:17:54] or three copies for fault tolerance,
[01:17:56] that means no matter what, you need to
[01:17:58] write one copy of the data across the
[01:18:00] network to a different server.
[01:18:02] So, there's a lot of network
[01:18:03] communication here, um and a bunch here
[01:18:05] also.
[01:18:06] Um and it was this network communication
[01:18:08] that really limited the throughput of
[01:18:09] MapReduce in 2004.
[01:18:12] Um
[01:18:14] in 2020,
[01:18:16] because this network arrangement was
[01:18:19] such a limiting factor for so many
[01:18:20] things people wanted to do in data
### chunk 114 [01:18:20]
Lecture 1: Introduction > Transcript

such a limiting factor for so many
[01:18:20] things people wanted to do in data[01:18:22] centers, modern data center networks are
[01:18:24] a lot faster at the root than this was.
[01:18:27] And so, um
[01:18:28] you know, one typical data center
[01:18:30] network you might see today actually has
[01:18:31] many root. Instead of a single root
[01:18:33] switch that everything has to go
[01:18:34] through, you might have
[01:18:36] uh
[01:18:37] you know many root switches and each
[01:18:40] rack switch has a connection to each of
[01:18:42] these sort of replicated root switches
[01:18:44] and the traffic is split up among the
[01:18:46] root switches. So modern data center
[01:18:47] networks
[01:18:49] have far more network throughput
[01:18:52] and because of that actually modern I
[01:18:54] think Google sort of stopped using
### chunk 115 [01:18:54]
Lecture 1: Introduction > Transcript

 because of that actually modern I
[01:18:54] think Google sort of stopped using[01:18:56] MapReduce a few years ago but um
[01:18:59] before they stopped using it the modern
[01:19:01] MapReduce actually no longer try to run
[01:19:03] the maps on the same machine as the data
[01:19:06] was stored on. They were happy to load
[01:19:07] the data from anywhere because they just
[01:19:09] assumed the network
[01:19:12] was extremely fast.
[01:19:14] Okay um
[01:19:16] We're out of time for MapReduce um
[01:19:19] We we have a lab
[01:19:21] due at the end of next week in which
[01:19:22] you'll write your own
[01:19:24] somewhat simplified MapReduce
[01:19:26] so have fun with that
[01:19:30] and see you on Thursday.
