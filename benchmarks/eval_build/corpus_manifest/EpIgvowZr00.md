# Lecture 3: GFS
- video_id: EpIgvowZr00
- document_id: 31282017576140cd8231eca72f90849f
- platform: youtube
- duration: 4942s (82m22s)
- chunk_count: 104
- language_guess: en

## L3 brief
This text summarizes the architectural design, operational workflows, consistency model, and key trade-offs of the Google File System as presented in an MIT distributed systems lecture.

## L2 summary
This document provides a comprehensive overview of the Google File System (GFS) based on a lecture segment from MIT 6.824. It details the architecture of GFS, which features a single master node managing metadata in memory and multiple chunkservers storing large files split into 64 MB chunks across low-cost hardware. The text explains the operational workflows for client reads, writes, and record appends, emphasizing lease assignments, version numbers, and client-side caching. Furthermore, it addresses the system's design trade-offs—such as prioritizing high sequential throughput and automated failure recovery over strict consistency and low latency—and outlines real-world limitations including master RAM exhaustion, potential duplicate or inconsistent data, and single-master bottlenecks.

## Chunks
### chunk 0 [00:00]
Lecture 3: GFS > Transcript

[00:00] I'd like to get started today we're
[00:05] gonna talk about GFS the Google file
[00:09] system paper we read for today
[00:10] and this will be the first of a number
[00:12] of different sort of case studies we'll
[00:15] talk about in this course about how to
[00:17] be build big storage systems so the
[00:19] larger topic is big storage the reason
[00:29] is the storage is turned out to be a key
[00:31] abstraction you might you know if you
[00:34] didn't know already you might imagine
[00:35] that there could be all kinds of
[00:37] different you know important
[00:40] abstractions you might want to use for
[00:42] distributed systems but it's turned out
[00:43] that a simple storage interface is just
[00:47] incredibly useful and extremely general
### chunk 1 [00:47]
Lecture 3: GFS > Transcript

simple storage interface is just
[00:47] incredibly useful and extremely general[00:50] and so a lot of the thought that's gone
[00:51] into building distributed systems has
[00:53] either gone into designing storage
[00:55] systems or designing other systems that
[00:57] assume underneath them some sort of
[01:00] reasonably well behaved big just
[01:02] distributed storage system so we're
[01:05] going to care a lot about how the you
[01:07] know how to design a good interface to a
[01:09] big storage system and how to design the
[01:12] innards of the storage system so it has
[01:14] good behavior you know of course that's
[01:18] why we're reading this paper just to get
[01:19] a start on that the this paper also
[01:20] touches on a lot of themes that will
[01:22] come up a lot in a tube for parallel
[01:24] performance fault tolerance replication
### chunk 2 [01:24]
Lecture 3: GFS > Transcript

 up a lot in a tube for parallel
[01:24] performance fault tolerance replication[01:27] and consistency and this paper is as
[01:31] such things go reasonably
[01:34] straightforward and easy to understand
[01:36] it's also a good systems paper it sort
[01:38] of talks about issues all the way from
[01:40] the hardware to the software that
[01:43] ultimately uses the system and it's a
[01:45] successful real world design so it says
[01:49] you know academic paper published in an
[01:51] academic conference but it describes
[01:53] something that really was successful and
[01:54] used for a long time in the real world
[01:57] so we sort of know that we're talking
[01:58] about something that is it's a good a
[02:02] good useful design okay so before I'm
[02:07] gonna talk about GFS I want to sort of
[02:09] talk about the space of distributed
### chunk 3 [02:09]
Lecture 3: GFS > Transcript

nna talk about GFS I want to sort of
[02:09] talk about the space of distributed[02:11] storage systems a little bit
[02:13] set the scene so first why is it hard
[02:19] it's actually a lot to get right but for
[02:23] a 2/4 there's a particular sort of
[02:25] narrative that's gonna come up quite a
[02:28] lot for many systems often the starting
[02:32] point for people designing these sort of
[02:34] big distributed systems or big storage
[02:35] systems is they want to get huge
[02:37] aggregate performance be able to harness
[02:39] the resources of hundreds of machines in
[02:43] order to get a huge amount of work done
[02:44] so the sort of starting point is often
[02:48] performance and you know if you start
[02:54] there a natural next thought is well
[02:57] we're gonna split our data over a huge
[02:59] number of servers in order to be able to
### chunk 4 [02:59]
Lecture 3: GFS > Transcript

onna split our data over a huge
[02:59] number of servers in order to be able to[03:00] read many servers in parallel so we're
[03:04] gonna get and that's often called
[03:05] sharding if you shard over many servers
[03:11] hundreds or thousands of servers you're
[03:13] just gonna see constant faults right if
[03:15] you have thousands of servers there's
[03:17] just always gonna be one down so we
[03:20] defaults are just every day every hour
[03:25] occurrences and we need automatic
[03:27] weekend of humans involved and fixing
[03:29] this fault we need automatic
[03:31] fault-tolerant systems so that leads to
[03:38] fault tolerance the among the most
[03:43] powerful ways to get fault tolerance is
[03:44] with replication just keep two or three
[03:46] or whatever copies of data one of them
[03:48] fails you can use another one so we want
### chunk 5 [03:48]
Lecture 3: GFS > Transcript

ever copies of data one of them
[03:48] fails you can use another one so we want[03:52] to have tolerance that leads to
[03:56] replication if you have replication two
[04:03] copies the data then you know for sure
[04:05] if you're not careful they're gonna get
[04:07] out of sync and so what you thought was
[04:09] two replicas of the data where you could
[04:10] use either one interchangeably to
[04:12] tolerate faults if you're not careful
[04:14] what you end up with is two almost
[04:15] identical replicas of the data that's
[04:18] like not exactly replicas at all and
[04:20] what you get back depends on which one
[04:22] you talk to so that's starting to maybe
[04:24] look a little bit
[04:25] tricky for applications to use so if we
[04:28] have replication we risk weird
[04:34] inconsistencies of course clever design
### chunk 6 [04:34]
Lecture 3: GFS > Transcript

] have replication we risk weird
[04:34] inconsistencies of course clever design[04:41] you can get rid of inconsistency and
[04:45] make the data look very well-behaved but
[04:47] if you do that it almost always requires
[04:49] extra work and extra sort of chitchat
[04:51] between all the different servers and
[04:53] clients in the network that reduces
[04:54] performance so if you want consistency
[04:59] you pay for with low performance I which
[05:09] is of course not what we originally
[05:11] hoping for of course this is an absolute
[05:13] you can build very high performance
[05:14] systems but nevertheless there's this
[05:16] sort of inevitable way that the design
[05:19] of these systems play out and it results
[05:21] in a tension between the original goals
[05:24] of performance and the sort of
[05:26] realization that if you want good
### chunk 7 [05:24]
Lecture 3: GFS > Transcript

[05:24] of performance and the sort of
[05:26] realization that if you want good[05:29] consistency you're gonna pay for it and
[05:31] if you don't want to pay for it then you
[05:33] have to suffer with sort of anomalous
[05:35] behavior sometimes I'm putting this up
[05:37] because we're gonna see this this loop
[05:39] many times for many of the systems we
[05:42] look we look at people are we're rarely
[05:45] willing to or happy about paying the
[05:48] full cost of very good consistency ok so
[05:52] you know with brought a consistency I'll
[05:57] talk more later in the course about more
[06:02] exactly what I mean by good consistency
[06:04] but you can think of strong consistency
[06:07] or good consistency as being we want to
[06:09] build a system whose behavior to
[06:11] applications or clients looks just like
### chunk 8 [06:11]
Lecture 3: GFS > Transcript

build a system whose behavior to
[06:11] applications or clients looks just like[06:13] you'd expect from talking to a single
[06:15] server all right we're gonna build you
[06:18] know systems out of hundreds of machines
[06:20] but a kind of ideal strong consistency
[06:23] model would be what you'd get if there
[06:25] was just one server with one copy of the
[06:26] data doing one thing at a time so this
[06:31] is kind of a strong
[06:34] consistency kind of intuitive way to
[06:41] think about strong consistency so you
[06:42] might think you have one server we'll
[06:45] assume that's a single-threaded server
[06:47] and that it processes requests from
[06:49] clients one at a time and that's
[06:50] important because there may be lots of
[06:52] clients sending concurrently requests
[06:55] into the server and see some current
### chunk 9 [06:55]
Lecture 3: GFS > Transcript

ients sending concurrently requests
[06:55] into the server and see some current[06:57] requests it picks one or the other to go
[06:59] first and excuse that request to
[07:00] completion then excuse the nets so for
[07:04] storage servers or you know the server's
[07:06] got a disk on it and what it means to
[07:07] process a request is it's a write
[07:10] request you know which might be writing
[07:12] an item or may be increment and I mean
[07:14] incrementing an item if it's a mutation
[07:17] then we're gonna go and we have some
[07:21] table of data and you know maybe index
[07:23] by keys and values and we're gonna
[07:25] update this table and if the request
[07:27] comes in and to read we're just gonna
[07:28] you know pull the write data out of the
[07:30] table one of the rules here that sort of
[07:36] makes this well-behaved is that each is
### chunk 10 [07:36]
Lecture 3: GFS > Transcript

e of the rules here that sort of
[07:36] makes this well-behaved is that each is[07:39] that the server really does execute in
[07:41] our simplified model excuse to request
[07:44] one at a time and that requests see data
[07:48] that reflects all the previous
[07:49] operations in order so if a sequence of
[07:51] writes come in and the server process
[07:53] them in some order then when you read
[07:55] you see the sort of you know value you
[07:58] would expect if those writes that
[08:00] occurred one at a time the behavior this
[08:05] is still not completely straightforward
[08:07] there's some you know there's some
[08:09] things that you have to spend at least a
[08:11] second thinking about so for example if
[08:13] we have a bunch of clients and client
[08:19] one issues a write of value X and wants
[08:25] it to set it to one and at the same time
### chunk 11 [08:25]
Lecture 3: GFS > Transcript

es a write of value X and wants
[08:25] it to set it to one and at the same time[08:27] client two issues the right of the same
[08:30] value but wants to set it to a different
[08:32] the same key but wants to set it to a
[08:34] different value right
[08:35] something happens let's say client three
[08:38] reads and get some result or client
[08:42] three after these writes complete reads
[08:44] get some result client four
[08:47] reads X and get some also gets a result
[08:50] so what results should the two clients
[08:51] see yeah
[09:04] well that's a good question so these
[09:07] what I'm assuming here is that client
[09:09] one inclined to launch these requests at
[09:10] the same time so if we were monitoring
[09:12] the network we'd see two requests
[09:14] heading to the server at the same time
[09:16] and then sometime later the server would
### chunk 12 [09:16]
Lecture 3: GFS > Transcript

 to the server at the same time
[09:16] and then sometime later the server would[09:19] respond to them
[09:20] so there's actually not enough here to
[09:23] be able to say whether the client would
[09:26] receipt would process the first request
[09:28] first which order there's not enough
[09:30] here to tell which order the server
[09:32] processes them in and of course if it
[09:35] processes this request first then that
[09:38] means or it processes the right with
[09:41] value to second and that means that
[09:43] subsequent reads have to see to where is
[09:46] it the server happened to process this
[09:48] request first and this one's second that
[09:50] means the resulting value better be one
[09:52] and these these two requests and see
[09:53] what so I'm just putting this up to sort
[09:56] of illustrate that even in a simple
### chunk 13 [09:56]
Lecture 3: GFS > Transcript

 so I'm just putting this up to sort
[09:56] of illustrate that even in a simple[09:58] system there's ambiguity you can't
[10:01] necessarily tell from trace of what went
[10:04] into the server or what should come out
[10:05] all of you can tell is that some set of
[10:08] results is consistent or not consistent
[10:11] with a possible execution so certainly
[10:13] there's some completely wrong results we
[10:17] can see go by it you know if client 3
[10:21] sees a 2 then client 4 I bet had better
[10:24] see it too also because our model is
[10:27] well after the second right you know
[10:29] climb trees these are two that means
[10:30] this right must have been second and it
[10:33] still had better be it still has to have
[10:35] been the second right one client 4 goes
[10:37] to the date so hopefully all this is
[10:41] just completely straightforward and just
### chunk 14 [10:41]
Lecture 3: GFS > Transcript

e date so hopefully all this is
[10:41] just completely straightforward and just[10:43] as expected because it's it's supposed
[10:47] to be the intuitive model of strong
[10:49] consistency ok and so the problem with
[10:53] this of course is that a single server
[10:54] has poor fault tolerance right if it
[10:56] crashes or it's disk dies or something
[10:57] we're left with nothing and so in the
[11:00] real world of distributed systems we
[11:02] actually build replicated systems so and
[11:05] that's where all the problems start
[11:06] leaking in is when we have a second
[11:08] copying data so here is what must be
[11:12] close to the worst replication design
[11:16] and I'm doing this to warn you of the
[11:19] problems that we will then be looking
[11:20] for in GFS all right so here's a bad
[11:23] replication design we're gonna have two
### chunk 15 [11:23]
Lecture 3: GFS > Transcript

in GFS all right so here's a bad
[11:23] replication design we're gonna have two[11:30] servers now each with a complete copy of
[11:32] the data and so on disks that are both
[11:38] gonna have this this table of keys and
[11:40] values the intuition of course is that
[11:44] we want to keep these tables we hope to
[11:47] keep these tables identical so that if
[11:49] one server fails we can read or write
[11:51] from the other server and so that means
[11:53] that somehow every write must be
[11:55] processed by both servers and reads have
[11:59] to be able to be processed by a single
[12:00] server otherwise it's not fault tolerant
[12:02] all right if reads have to consult both
[12:04] and we can't survive the loss of one of
[12:07] the servers okay so the problem is gonna
[12:13] come up well I suppose we have client 1
### chunk 16 [12:13]
Lecture 3: GFS > Transcript

ers okay so the problem is gonna
[12:13] come up well I suppose we have client 1[12:17] and client 2 and they both want to do
[12:19] these right say one of them gonna write
[12:20] one and the other is going to write two
[12:22] so client 1 is gonna launch it's right
[12:25] x1 2 both because we want to update both
[12:29] of them and climb 2 is gonna launch it's
[12:32] write X so what's gonna go wrong here
[12:41] yeah yeah we haven't done anything here
[12:46] to ensure that the two servers process
[12:48] the two requests in the same order right
[12:51] that's a bad design
[12:53] so if server 1 processes client ones
[12:57] request first it'll end up it'll start
[13:01] with a value of 1 and then it'll see
[13:02] client twos request and overwrite that
[13:04] with 2 if server 2 just happens to
[13:07] receive the packets over the network in
### chunk 17 [13:07]
Lecture 3: GFS > Transcript

th 2 if server 2 just happens to
[13:07] receive the packets over the network in[13:09] a different order it's going to execute
[13:11] client 2's requests and set the value to
[13:13] 2 and then then it will see client ones
[13:15] request set the value to 1 and now what
[13:18] a client a later reading client sees you
[13:20] know if client 3 happens to reach from
[13:22] this server and client for happens to
[13:25] reach from the other server then we get
[13:26] into this terrible situation where
[13:28] they're gonna read different values even
[13:30] though our intuitive model of a correct
[13:33] service says they both subsequent reads
[13:35] hefty you're the same value and this can
[13:39] arise in other ways you know suppose we
[13:41] try to fix this by making the clients
[13:43] always read from server one if it's up
### chunk 18 [13:43]
Lecture 3: GFS > Transcript

to fix this by making the clients
[13:43] always read from server one if it's up[13:45] and otherwise server two if we do that
[13:48] then if this situation happened and four
[13:51] why oh yeah both everybody reads might
[13:53] see client might see value too but a
[13:55] server one suddenly fails then even
[13:57] though there was no right suddenly the
[14:00] value for X we'll switch from 2 to 1
[14:02] because if server 1 died it's all the
[14:04] clients assistant server 2 no but just
[14:07] this mysterious change in the data that
[14:09] doesn't correspond to any right which is
[14:11] also totally not something that could
[14:13] have happened in this service simple
[14:15] server model all right so of course this
[14:23] can be fixed the fix requires more
[14:25] communication usually between the
[14:28] servers or somewhere more complexity and
### chunk 19 [14:28]
Lecture 3: GFS > Transcript

mmunication usually between the
[14:28] servers or somewhere more complexity and[14:33] because of the cost of inevitable cost
[14:36] to the complexity to get strong
[14:37] consistency there's a whole range of
[14:41] different solutions to get better
[14:43] consistency and a whole range of what
[14:45] people feel is an acceptable level of
[14:48] consistency in an acceptable sort of a
[14:52] set of anomalous behaviors that might be
[14:54] revealed all right any questions about
[14:57] this disastrous model here
[15:04] okay that's what you're talking about
[15:07] GFS a lot of thought about doing GFS was
[15:13] doing is fixing this they had better but
[15:17] not perfect behavior okay so where GFS
[15:21] came from in 2003 quite a while ago
[15:24] actually at that time the the web you
[15:27] know was certainly starting to be a very
### chunk 20 [15:27]
Lecture 3: GFS > Transcript

ly at that time the the web you
[15:27] know was certainly starting to be a very[15:29] big deal and people are building big
[15:31] websites in addition there had been
[15:35] decades of research into distributed
[15:37] systems and people sort of knew at least
[15:39] at the academic level how to build all
[15:40] kinds of highly parallel fault tolerant
[15:43] whatever systems but there been very
[15:44] little use of academic ideas in industry
[15:49] but starting at around the time this
[15:52] paper was published big websites like
[15:54] Google started to actually build serious
[15:57] distributed systems and it was like very
[16:01] exciting for people like me who were I'm
[16:03] a kid I'm excited this to see see real
[16:06] uses of these ideas where Google was
[16:10] coming from was you know they had some
[16:11] vast vast data sets far larger than
### chunk 21 [16:11]
Lecture 3: GFS > Transcript

ming from was you know they had some
[16:11] vast vast data sets far larger than[16:14] could be stored in a single disk like an
[16:16] entire crawl copy of the web or a little
[16:20] bit after this paper they had giant
[16:22] YouTube videos they had things like the
[16:25] intermedia files for building a search
[16:27] index
[16:28] they also apparently kept enormous log
[16:30] files from all their web servers so they
[16:32] could later analyze them so they had
[16:34] some big big data sets they used both to
[16:36] store them and many many disks to store
[16:39] them and they needed to be able to
[16:41] process them quickly with things like
[16:42] MapReduce so they needed high speed
[16:44] parallel access to these vast amounts of
[16:47] data okay so what they were looking for
[16:51] one goal was just that the thing be big
### chunk 22 [16:51]
Lecture 3: GFS > Transcript

ay so what they were looking for
[16:51] one goal was just that the thing be big[16:53] and fast they also wanted a file system
[17:00] that was sort of global in the sense
[17:02] that many different applications could
[17:04] get at it one way to build a big storage
[17:06] system is to you know you have some
[17:07] particular application or mining you
[17:09] build storage sort of dedicated and
[17:11] tailored to that application and if
[17:13] somebody else in the next office needs
[17:14] big storage well they can build their
[17:17] own thing
[17:17] right but if you have a universal or
[17:21] kind of global reusable storage system
[17:25] and that means that if I store a huge
[17:28] amount of data si you know I'm crawling
[17:29] the web and you want to look at my
[17:31] crawled web web pages because we're all
[17:35] using we're all playing in the same
### chunk 23 [17:35]
Lecture 3: GFS > Transcript

wled web web pages because we're all
[17:35] using we're all playing in the same[17:36] sandbox we're all using the same storage
[17:38] system you can just read my files you
[17:40] know maybe access controls permitting so
[17:43] the idea was to build a sort of file
[17:45] system where anybody you know anybody
[17:47] inside Google could name and read any of
[17:50] the files to allow sharing in order to
[17:57] get a in order to get bigness and
[17:58] fastness they need to split the data
[18:00] through every file will be automatically
[18:04] split by GFS over many servers so that
[18:07] writes and reads would just
[18:08] automatically be fast as long as you
[18:10] were reading from lots and lots of
[18:12] reading a file from lots of clients you
[18:14] get high aggregate throughput and also
[18:17] be able to for a single file be able to
### chunk 24 [18:17]
Lecture 3: GFS > Transcript

gh aggregate throughput and also
[18:17] be able to for a single file be able to[18:20] have single files that were bigger than
[18:21] any single disk because we're building
[18:24] something out of hundreds of servers we
[18:26] want automatic feel your recovery we
[18:36] don't want to build a system where every
[18:37] time one of our hundreds of servers a
[18:38] fail some human being has to go to the
[18:40] machine room and do something with the
[18:42] server or to get it up and running or
[18:44] transfers data or something well this
[18:46] isn't just fix itself um there were some
[18:50] sort of non goals like one is that GFS
[18:54] was designed to run in a single data
[18:55] center so we're not talking about
[18:57] placing replicas all over the world a
[18:59] single GFS installation just lived in
[19:02] one one data center one big machine run
### chunk 25 [19:02]
Lecture 3: GFS > Transcript

e GFS installation just lived in
[19:02] one one data center one big machine run[19:05] so getting this style system to work
[19:12] where the replicas are far distant from
[19:14] each other is a valuable goal but
[19:17] difficult so single data centers this is
[19:22] not a service to customers GFS was for
[19:25] internal use by
[19:27] applications written by Google engineers
[19:30] so it wasn't they weren't directly
[19:32] selling this they might be selling
[19:33] services they used GFS internally but
[19:37] they weren't selling it directly so it's
[19:38] just for internal use and it was
[19:45] tailored in a number of ways for big
[19:48] sequential file reads and writes there's
[19:51] a whole nother domain like a system of
[19:54] storage systems that are optimized for
[19:56] small pieces of data like a bank that's
### chunk 26 [19:56]
Lecture 3: GFS > Transcript

e systems that are optimized for
[19:56] small pieces of data like a bank that's[19:58] holding bank balances probably wants a
[20:00] database that can read and write an
[20:02] update you know 100 byte records that
[20:04] hold people's bank balances but GFS is
[20:07] not that system so it's really for big
[20:10] or big is you know terabytes gigabytes
[20:12] some big sequential not random access
[20:22] it's also that has a certain batch
[20:24] flavor there's not a huge amount of
[20:26] effort to make access be very low
[20:27] latency the focus is really on
[20:30] throughput of big you know multi
[20:32] megabyte operations this paper was
[20:36] published at s OSP in 2003 the top
[20:39] systems academic conference yeah usually
[20:46] the standard for papers such conferences
[20:49] they have you know a lot of very novel
### chunk 27 [20:49]
Lecture 3: GFS > Transcript

ndard for papers such conferences
[20:49] they have you know a lot of very novel[20:51] research this paper was not necessarily
[20:54] in that class the specific ideas in this
[20:55] paper none of them are particularly new
[20:57] at the time and things like distribution
[21:00] and sharding and fault tolerance were
[21:02] you know well understood had to had to
[21:05] deliver those but this paper described a
[21:07] system that was really operating in in
[21:09] use at a far far larger scale hundreds
[21:11] of thousands of machines much bigger
[21:13] than any you know academics ever built
[21:16] the fact that it was used in industry
[21:18] and reflected real world experience of
[21:21] like what actually didn't didn't work
[21:23] for deployed systems that had to work
[21:25] and had to be cost effective also like
[21:28] extremely valuable the paper sort of
### chunk 28 [21:28]
Lecture 3: GFS > Transcript

 had to be cost effective also like
[21:28] extremely valuable the paper sort of[21:34] proposed a fairly heretical view that it
[21:39] was okay for the storage system to have
[21:40] pretty
[21:41] consistency we the academic mindset at
[21:45] that time was the you know the storage
[21:46] system really should have good behavior
[21:47] like what's the point of building
[21:48] systems that sort of return the wrong
[21:50] data like my terrible replication system
[21:53] like why do that why not build systems
[21:55] return the right data correct data
[21:57] instead of incorrect data now with this
[21:59] paper actually does not guarantee return
[22:02] correct data and you know the hope is
[22:05] that they take advantage of that in
[22:07] order to get better performance I'm a
[22:09] final thing that was sort of interesting
### chunk 29 [22:09]
Lecture 3: GFS > Transcript

to get better performance I'm a
[22:09] final thing that was sort of interesting[22:11] about this paper is its use of a single
[22:13] master in a sort of academic paper you
[22:16] probably have some fault-tolerant
[22:18] replicated automatic failure recovering
[22:20] master perhaps many masters with the
[22:24] work split open um but this paper said
[22:25] look you know you they can get away with
[22:26] a single master and it worked fine well
[22:39] cynically you know who's going to notice
[22:40] on the web that some vote count or
[22:43] something is wrong or if you do a search
[22:44] on a search engine now you're gonna know
[22:47] that oh you know like one of 20,000
[22:50] items is missing from the search results
[22:51] or they're in the wrong order probably
[22:54] not so there was just much more
[22:58] tolerance in these kind of systems than
### chunk 30 [22:58]
Lecture 3: GFS > Transcript

 not so there was just much more
[22:58] tolerance in these kind of systems than[22:59] there would like in a bank for incorrect
[23:02] data it doesn't mean that all data and
[23:04] websites can be wrong like if you're
[23:05] charging people for ad impressions you
[23:07] better get the numbers right but this is
[23:09] not really about that in addition some
[23:15] of the ways in which GFS could serve up
[23:18] odd data could be compensated for in the
[23:21] applications like where the paper says
[23:23] you know applications should accompany
[23:25] their data with check sums and clearly
[23:28] mark record boundaries that's so the
[23:30] applications can recover from GFS
[23:32] serving them maybe not quite the right
[23:35] data
[23:40] all right so the general structure and
[23:44] this is just figure one in the paper so
### chunk 31 [23:44]
Lecture 3: GFS > Transcript

ght so the general structure and
[23:44] this is just figure one in the paper so[23:48] we have a bunch of clients hundreds
[23:53] hundreds of clients we have one master
[23:59] although there might be replicas of the
[24:02] master the master keeps the mapping from
[24:07] file names to where to find the data
[24:09] basically although there's really two
[24:10] tables so and then there's a bunch of
[24:14] chunk servers maybe hundreds of chunk
[24:18] servers each with perhaps one or two
[24:21] discs the separation here's the master
[24:23] is all about naming and knowing where
[24:25] the chunks are and the chunk servers
[24:27] store the actual data this is like a
[24:29] nice aspect of the design that these two
[24:31] concerns are almost completely separated
[24:32] from each other and can be designed just
[24:35] separately with separate properties the
### chunk 32 [24:35]
Lecture 3: GFS > Transcript

h other and can be designed just
[24:35] separately with separate properties the[24:41] master knows about all the files for
[24:43] every file the master keeps track of a
[24:44] list of chunks chunk identifiers that
[24:48] contain the successive pieces that file
[24:50] each chunk is 64 megabytes so if I have
[24:53] a you know gigabyte file the master is
[24:57] gonna know that maybe the first chunk is
[24:58] stored here and the second chunk is
[25:00] stored here the third chunk is stored
[25:01] here and if I want to read whatever part
[25:03] of the file I need to ask the master oh
[25:05] which server hole is that chunk and I go
[25:07] talk to that server and read the chunk
[25:09] roughly speaking all right so more
[25:17] precisely we need to turns out if we're
[25:21] going to talk about how the system about
### chunk 33 [25:21]
Lecture 3: GFS > Transcript

y we need to turns out if we're
[25:21] going to talk about how the system about[25:23] the consistency of the system and how it
[25:24] deals with false we need to know what
[25:27] the master is actually storing in a
[25:29] little bit more detail so the master
[25:31] data
[25:36] it's got two main tables that we care
[25:38] about it's got one table that map's file
[25:41] name to an array of chunk IDs or chunk
[25:52] handles this just tells you where to
[26:00] find the data or what the what the
[26:03] identifiers are the chunks are so it's
[26:05] not much yet you can do with a chunk
[26:06] identifier but the master also happens
[26:08] to have a a second table that map's
[26:11] chunk handles each chunk handle to a
[26:17] bunch of data about that chunk so one is
[26:21] the list of chunk servers that hold
[26:23] replicas of that data each chunk is
### chunk 34 [26:23]
Lecture 3: GFS > Transcript

 the list of chunk servers that hold
[26:23] replicas of that data each chunk is[26:25] stored on more than one chunk server so
[26:28] it's a list chunk servers every chunk
[26:39] has a current version number so this
[26:42] master has a remembers the version
[26:46] number for each chunk all rights for a
[26:50] chunk have to be sequence ooh the chunks
[26:51] primary it's one of the replicas so
[26:54] master remembers the rich chunk servers
[26:58] the primary and there's also that
[27:00] primary is only allowed to be primary
[27:02] for a certain least time so the master
[27:05] remembers the expiration time of the
[27:13] lease this stuff so far it's all in RAM
[27:17] and the master so just be gone if the
[27:19] master crashed so in order that you'd be
[27:24] able to reboot the master and not forget
[27:26] everything about the file system the
### chunk 35 [27:26]
Lecture 3: GFS > Transcript

to reboot the master and not forget
[27:26] everything about the file system the[27:29] master actually stores all of this data
[27:30] on disk as well as in memory so reads
[27:35] just come from memory but writes to at
[27:38] least the parts of this data that had to
[27:40] be reflected on this writes have to go
[27:42] to the disk so and the way it actually
[27:45] managed that is that there's all
[27:47] the master has a log on disk and every
[27:51] time it changes the data it appends an
[27:53] entry to the log on disk and checkpoint
[28:04] so some of this stuff actually needs to
[28:07] be on disk and some doesn't it turns out
[28:10] I'm guessing a little bit here but
[28:12] certainly the array of chunk handles has
[28:16] to be on disk and so I'm gonna write env
[28:18] here for non-volatile meaning it it's
[28:20] got to be reflected on disk the list of
### chunk 36 [28:20]
Lecture 3: GFS > Transcript

for non-volatile meaning it it's
[28:20] got to be reflected on disk the list of[28:22] chunk servers it turns out doesn't
[28:25] because the master if it reboots talks
[28:28] to all the chunk servers and ask them
[28:29] what chunks they have so this is I
[28:32] imagine not written to disk the version
[28:36] number any guesses written to disk not
[28:38] written to disk requires knowing how the
[28:42] system works I'm gonna vote written to
[28:51] disk non-volatile we can argue about
[28:55] that later when we talk about how system
[28:57] works identity the primary it turns out
[29:04] not almost certainly not written to disk
[29:06] so volatile and the reason is the master
[29:10] is um reboots and forgets therefore
[29:13] since it's volatile forgets who the
[29:15] primary is for a chunk it can simply
[29:17] wait for the 62nd lease expiration time
### chunk 37 [29:17]
Lecture 3: GFS > Transcript

ary is for a chunk it can simply
[29:17] wait for the 62nd lease expiration time[29:19] and then it knows that absolutely no
[29:21] primary will be functioning for this
[29:23] chunk and then it can designate a
[29:24] different primary safely and similarly
[29:27] the lease expiration stuff is volatile
[29:29] so that means that whenever a file is
[29:32] extended with a new chunk goes to the
[29:35] next 64 megabyte boundary or the version
[29:40] number changes because the new primary
[29:42] is designated that means that the master
[29:45] has to first append a little record to
[29:48] his log basically saying oh I just added
[29:50] a such-and-such a chunk to this file or
[29:53] I just changed the version number so
[29:56] every time I change is one of those that
[29:57] needs to writes right it's disk so this
[29:59] is paper doesn't talk about this
### chunk 38 [29:59]
Lecture 3: GFS > Transcript

needs to writes right it's disk so this
[29:59] is paper doesn't talk about this[30:00] much but you know there's limits the
[30:02] rate at which the master can change
[30:05] things because you can only write your
[30:07] disk however many times per second and
[30:09] the reason for using a log rather than a
[30:12] database you know some sort of b-tree or
[30:16] hash table on disk is that you can
[30:20] append to a log very efficiently because
[30:24] you only need you can take a bunch of
[30:26] recent log records they need to be added
[30:28] and sort of write them all on a single
[30:29] write after a single rotation to
[30:32] whatever the point in the disk is that
[30:33] contains the end of the log file whereas
[30:36] if it were a sort of b-tree reflecting
[30:38] the real structure of this data then you
[30:42] would have to seek to a random place in
### chunk 39 [30:42]
Lecture 3: GFS > Transcript

 structure of this data then you
[30:42] would have to seek to a random place in[30:43] the disk and do a little right so the
[30:45] log makes a little bit faster to write
[30:46] there to reflect operations on to the
[30:51] disk however if the master crashes and
[30:56] has to reconstruct its state you
[30:58] wouldn't want to have to reread its log
[31:00] file back starting from the beginning of
[31:02] time from when the server was first
[31:04] installed you know a few years ago so in
[31:06] addition the master sometimes
[31:08] checkpoints its complete state to disk
[31:10] which takes some amount of time seconds
[31:15] maybe a minute or something and then
[31:17] when it restarts what it does is goes
[31:20] back to the most recent checkpoint and
[31:21] plays just the portion of a log that
[31:24] sort of starting at the point in time
### chunk 40 [31:24]
Lecture 3: GFS > Transcript

ays just the portion of a log that
[31:24] sort of starting at the point in time[31:26] when that check one is created any
[31:30] questions about the master data okay
[31:40] so with that in mind I'm going to lay
[31:44] out the steps in a read and the steps in
[31:46] the right
[31:46] where all this is heading is that I then
[31:49] want to discuss you know for each
[31:50] failure I can think of why does the
[31:53] system or does the system act directly
[31:56] after that failure um but in order to do
[31:58] that we need to understand the data and
[32:00] operations in the data okay so if
[32:03] there's a read the first step is that
[32:11] the client and what a read means that
[32:12] the application has a file name in mind
[32:14] and an offset in the file that it wants
[32:17] to read some data front so it sends the
### chunk 41 [32:17]
Lecture 3: GFS > Transcript

offset in the file that it wants
[32:17] to read some data front so it sends the[32:19] file name and the offset to the master
[32:21] and the master looks up the file name in
[32:23] its file table and then you know each
[32:25] chunk is 64 megabytes who can use the
[32:28] offset divided by 64 megabytes to find
[32:30] which chunk and then it looks at that
[32:33] chunk in its chunk table finds the list
[32:39] of chunk servers that have replicas of
[32:41] that data and returns that list to the
[32:44] client so the first step is so you know
[32:52] the file name and the offset the master
[32:56] and the master sends the chunk handle
[33:05] let's say H and the list of servers so
[33:11] now we have some choice we can ask any
[33:13] one of these servers pick one that's and
[33:15] the paper says that clients try to guess
### chunk 42 [33:15]
Lecture 3: GFS > Transcript

ese servers pick one that's and
[33:15] the paper says that clients try to guess[33:17] which server is closest to them in the
[33:19] network maybe in the same rack and send
[33:23] the read request to that to that replica
[33:28] the client actually caches
[33:35] cassia's this result so that if it reads
[33:37] that chunk again and indeed the client
[33:39] might read a given chunk in you know one
[33:41] megabyte pieces or 64 kilobyte pieces or
[33:45] something so I may end up reading the
[33:47] same chunk different points successive
[33:49] regions of a chunk many times and so
[33:51] caches which server to talk to you for
[33:56] giving chunks so it doesn't have to keep
[33:57] beating on the master asking the master
[33:59] for the same information over and over
[34:03] now the client talks to one of the chunk
[34:07] servers tells us a chunk handling offset
### chunk 43 [34:07]
Lecture 3: GFS > Transcript

lient talks to one of the chunk
[34:07] servers tells us a chunk handling offset[34:12] and the chunk servers store these chunks
[34:16] each chunk in a separate Linux file on
[34:19] their hard drive in a ordinary Linux
[34:21] file system and presumably the chunk
[34:24] files are just named by the handle so
[34:26] all the chunk server has to do is go
[34:28] find the file with the right name you
[34:31] know I'll give it that
[34:33] entire chunk and then just read the
[34:35] desired range of bytes out of that file
[34:38] and return the data to the client I hate
[34:46] question about how reads operate can I
[34:51] repeat number one the step one is the
[34:54] application wants to read it a
[34:57] particular file at a particular offset
[35:00] within the file a particular range of
[35:02] bytes in the files and one thousand two
### chunk 44 [35:02]
Lecture 3: GFS > Transcript

n the file a particular range of
[35:02] bytes in the files and one thousand two[35:04] two thousand and so it just sends a name
[35:05] of the file and the beginning of the
[35:09] byte range to the master and then the
[35:12] master looks a file name and it's file
[35:14] table to find the chunk that contains
[35:18] that byte range for that file so good
[35:30] [Music]
[35:34] so I don't know the exact details my
[35:36] impression is that the if the
[35:38] application wants to read more than 64
[35:40] megabytes or even just two bytes but
[35:42] spanning a chunk boundary that the
[35:44] library so the applications linked with
[35:47] a library that sends our pcs to the
[35:52] various servers and that library would
[35:54] notice that the reads spanned a chunk
[35:56] boundary and break it into two separate
[35:58] reads and maybe talk to the master I
### chunk 45 [35:58]
Lecture 3: GFS > Transcript

dary and break it into two separate
[35:58] reads and maybe talk to the master I[36:01] mean it may be that you could talk to
[36:02] the master once and get two results or
[36:04] something but logically at least it two
[36:06] requests to the master and then requests
[36:08] to two different chunk servers yes well
[36:19] at least initially the client doesn't
[36:21] know for a given file
[36:26] what chunks need what chunks well it can
[36:35] calculate it needs the seventeenth chunk
[36:37] but but then it needs to know what chunk
[36:40] server holds the seventeenth chunk of
[36:42] that file and for that it certainly
[36:44] needs for that it needs to talk to the
[36:47] master okay so all right did I'm not
[36:58] going to make a strong claim about which
[36:59] of them decides that it was the
[37:01] seventeenth chunk in the file but it's
### chunk 46 [37:01]
Lecture 3: GFS > Transcript

] of them decides that it was the
[37:01] seventeenth chunk in the file but it's[37:03] the master that finds the identifier of
[37:06] the handle of the seventeenth chunk in
[37:07] the file looks that up in its table and
[37:09] figures out which chunk servers hold
[37:12] that chunk yes
[37:25] how does that or you mean if the if the
[37:35] client asks for a range of bytes that
[37:38] spans a chunk boundary yeah so the the
[37:46] well you know the client will ask that
[37:49] well the clients linked with this
[37:50] library is a GFS library that noticed
[37:52] how to take read requests apart and put
[37:56] them back together and so that library
[38:00] would talk to the master and the master
[38:01] would tell it well well you know chunk
[38:02] seven is on this server and chunk eight
[38:05] is on that server and then why the
### chunk 47 [38:05]
Lecture 3: GFS > Transcript

ven is on this server and chunk eight
[38:05] is on that server and then why the[38:07] library would just be able to say oh you
[38:09] know I need the last couple bites of
[38:10] chunk seven and the first couple bites
[38:12] of chunk eight and then would fetch
[38:15] those put them together in a buffer and
[38:17] return them to the calling application
[38:26] well the master tells it about chunks
[38:28] and the library kind of figures out
[38:30] where it should look in a given chunk to
[38:32] find the date of the application wanded
[38:34] the application only thinks in terms of
[38:36] file names and sort of just offsets in
[38:38] the entire file in the library and the
[38:41] master conspire to turn that into chunks
[38:45] yeah
[38:50] sorry let me get closer here you see
[38:55] again so the question is does it matter
### chunk 48 [38:55]
Lecture 3: GFS > Transcript

y let me get closer here you see
[38:55] again so the question is does it matter[39:03] which chunk server you reach room so you
[39:06] know yes and no notionally they're all
[39:08] supposed to be replicas in fact as you
[39:13] may have noticed or as we'll talk about
[39:14] they're not you know they're not
[39:17] necessarily identical and applications
[39:20] are supposed to be able to tolerate this
[39:21] but the fact is that you make a slightly
[39:23] different data depending on which
[39:24] replicas you read yeah so the paper says
[39:28] that clients try to read from the chunk
[39:32] server that's in the same rack or on the
[39:34] same switch or something all right so
[39:44] that's reads
[39:48] the rights are more complex and
[39:51] interesting now the application
[40:02] interface for rights is pretty similar
### chunk 49 [40:02]
Lecture 3: GFS > Transcript

] interesting now the application
[40:02] interface for rights is pretty similar[40:04] there's just some call some library you
[40:06] call to mate you make to the gfs client
[40:08] library saying look here's a file name
[40:10] and a range of bytes I'd like to write
[40:12] and the buffer of data that I'd like you
[40:14] to write to that that range actually let
[40:17] me let me backpedal I only want to talk
[40:19] about record of pens and so I'm going to
[40:23] praise this the client interface as the
[40:26] client makes a library call that says
[40:28] here's a file name and I'd like to
[40:29] append this buffer of bytes to the file
[40:32] I said this is the record of pens that
[40:35] the paper talks about so again the
[40:42] client asks the master look I want to
[40:47] append sends a master requesting what I
[40:49] would like to pen to this named file
### chunk 50 [40:49]
Lecture 3: GFS > Transcript

nd sends a master requesting what I
[40:49] would like to pen to this named file[40:51] please tell me where to look for the
[40:55] last chunk in the file because the
[40:56] client may not know how long the file is
[40:58] if lots of clients are opinion to the
[41:00] same file because we have some big file
[41:02] this logging stuff from a lot of
[41:04] different clients may be you know no
[41:06] client will necessarily know how long
[41:08] the file is and therefore which offset
[41:10] or which chunk it should be appending to
[41:12] so you can ask the master please tell me
[41:14] about the the server's that hold the
[41:16] very last chunk
[41:18] current chunk in this file so
[41:22] unfortunately now the writing if you're
[41:26] reading you can read from any up-to-date
[41:27] replica for writing though there needs
### chunk 51 [41:27]
Lecture 3: GFS > Transcript

 you can read from any up-to-date
[41:27] replica for writing though there needs[41:30] to be a primary so at this point on the
[41:32] file may or may not have a primary
[41:35] already designated by the master so we
[41:37] need to consider the case of if there's
[41:39] no primary already and all the master
[41:40] knows well there's no primary so so one
[41:49] case is no primary
[41:57] in that case the master needs to find
[42:00] out the set of chunk servers that have
[42:03] the most up-to-date copy of the chunk
[42:06] because know if you've been running the
[42:08] system for a long time due to failures
[42:10] or whatever there may be chunk servers
[42:11] out there that have old copies of the
[42:14] chunk from you know yesterday or last
[42:15] week that I've been kept up to kept up
[42:17] to date because maybe that server was
### chunk 52 [42:17]
Lecture 3: GFS > Transcript

 that I've been kept up to kept up
[42:17] to date because maybe that server was[42:19] dead for a couple days and wasn't
[42:21] receiving updates so there's you need to
[42:23] be able to tell the difference between
[42:24] up-to-date copies of the chunk and non
[42:27] up-to-date so the first step is to find
[42:33] you know find up-to-date this is all
[42:37] happening in the master because the
[42:41] client has asked the master told the
[42:42] master look I want up end of this file
[42:44] please tell me what chunk service to
[42:46] talk to so a part of the master trying
[42:48] to figure out what chunk servers the
[42:49] client should talk to you
[42:50] so when we finally find up-to-date
[42:52] replicas and what update means is a
[42:59] replica whose version of the chunk is
[43:02] equal to the version number that the
### chunk 53 [43:02]
Lecture 3: GFS > Transcript

plica whose version of the chunk is
[43:02] equal to the version number that the[43:04] master knows is the most up-to-date
[43:06] version number it's the master that
[43:08] hands out these version numbers the
[43:10] master remembers that oh for this
[43:14] particular chunk you know the trunk
[43:18] server is only up to date if it has
[43:19] version number 17 and this is why it has
[43:21] to be non-volatile stored on disk
[43:23] because if if it was lost in a crash and
[43:26] there were chunk servers holding stale
[43:31] copies of chunks the master wouldn't be
[43:33] able to distinguish between chunk
[43:35] servers holding stale copies of a chunk
[43:36] from last week and a chunk server that
[43:39] holds the copy of the chunk that was
[43:42] up-to-date as of the crash that's why
[43:44] the master members of version number on
[43:46] disk yeah
### chunk 54 [43:44]
Lecture 3: GFS > Transcript

ash that's why
[43:44] the master members of version number on
[43:46] disk yeah[43:54] if you knew you were talking to all the
[43:56] chunk servers okay so the observation is
[43:59] the master has to talk to the chunk
[44:02] servers anyway if it reboots in order to
[44:04] find which chunk server holds which
[44:06] chunk because the master doesn't
[44:08] remember that so you might think that
[44:12] you could just take the maximum you
[44:14] could just talk to the chunk servers
[44:15] find out what trunks and versions they
[44:17] hold and take the maximum for a given
[44:19] chunk overall the responding chunk
[44:20] servers and that would work if all the
[44:22] chunk servers holding a chunk responded
[44:24] but the risk is that at the time the
[44:26] master reboots maybe some of the chunk
[44:28] servers are offline or disconnected or
### chunk 55 [44:28]
Lecture 3: GFS > Transcript

r reboots maybe some of the chunk
[44:28] servers are offline or disconnected or[44:30] whatever themselves rebooting and don't
[44:32] respond and so all the master gets back
[44:35] is responses from chunk servers that
[44:38] have last week's copies of the block and
[44:40] the chunk servers that have the current
[44:42] copy haven't finished rebooting or
[44:44] offline or something so ok oh yes if if
[44:54] the server's holding the most recent
[44:56] copy are permanently dead if you've lost
[44:59] all copies all of the most recent
[45:02] version of a chunk then yes
[45:09] No
[45:11] okay so the question is the master knows
[45:15] that for this chunk is looking for
[45:17] version 17
[45:18] supposing it finds no chunk server you
[45:21] know and it talks to the chunk servers
[45:22] periodically to sort of ask them what
### chunk 56 [45:22]
Lecture 3: GFS > Transcript

 and it talks to the chunk servers
[45:22] periodically to sort of ask them what[45:24] chunks do you have what versions you
[45:25] have supposing it finds no server with
[45:27] chunk 17 with version 17 for this this
[45:30] chunk then the master will either say
[45:32] well either not respond yet and wait or
[45:35] it will tell the client look I can't
[45:39] answer that try again later and this
[45:42] would come up like there was a power
[45:44] failure in the building and all the
[45:45] server's crashed and we're slowly
[45:47] rebooting the master might come up first
[45:49] and you know some fraction of the chunk
[45:51] servers might be up and other ones would
[45:53] reboot five minutes from now but so we
[45:57] ask to be prepared to wait and it will
[45:59] wait forever because you don't want to
[46:02] use a stale version of that of a chunk
### chunk 57 [46:02]
Lecture 3: GFS > Transcript

forever because you don't want to
[46:02] use a stale version of that of a chunk[46:05] okay so the master needs to assemble the
[46:09] list of chunk servers that have the most
[46:10] recent version the master knows the most
[46:12] recent versions stored on disk each
[46:14] chunk server along with each chunk as
[46:16] you pointed out also remembers the
[46:18] version number of the chunk that it's
[46:19] stores so that when chunk slivers
[46:22] reported into the master saying look I
[46:23] have this chunk the master can ignore
[46:25] the ones whose version does not match
[46:27] the version the master knows is the most
[46:30] recent okay so remember we were the
[46:34] client want to append the master doesn't
[46:36] have a primary it figures out maybe you
[46:39] have to wait for the set of chunk
[46:42] servers that have the most recent
### chunk 58 [46:42]
Lecture 3: GFS > Transcript

:39] have to wait for the set of chunk
[46:42] servers that have the most recent[46:43] version of that chunk it picks a primary
[46:50] so I'm gonna pick one of them to be the
[46:52] primary and the others to be secondary
[46:56] servers
[46:56] among the replicas set at the most
[46:58] recent version the master then
[47:02] increments
[47:07] the version number and writes that to
[47:11] disk so it doesn't forget it the crashes
[47:13] and then it sends the primary in the
[47:15] secondaries and that's each of them a
[47:18] message saying look for this chunk
[47:20] here's the primary here's the
[47:22] secondaries you know recipient maybe one
[47:26] of them and here's the new version
[47:28] number so then it tells primary
[47:32] secondaries this information plus the
[47:37] version number the primaries and
[47:39] secondaries
### chunk 59 [47:37]
Lecture 3: GFS > Transcript

nformation plus the
[47:37] version number the primaries and
[47:39] secondaries[47:39] alright the version number to disk so
[47:41] they don't forget because you know if
[47:43] there's a power failure or whatever they
[47:45] have to report in to the master with the
[47:47] actual version number they hold yes
[48:04] that's a great question
[48:06] so I don't know there's hints in the
[48:08] paper that I'm slightly wrong about this
[48:11] so the paper says I think your question
[48:14] was explaining something to me about the
[48:16] paper the paper says if the master
[48:18] reboots and talks to chunk servers and
[48:22] one of the chunk servers reboot reports
[48:24] a version number that's higher than the
[48:26] version number the master remembers the
[48:28] master assumes that there was a failure
[48:31] while it was assigning a new primary and
### chunk 60 [48:31]
Lecture 3: GFS > Transcript

ssumes that there was a failure
[48:31] while it was assigning a new primary and[48:34] adopts the new the higher version number
[48:36] that it heard from a chunk server so it
[48:38] must be the case that in order to handle
[48:42] a master crash at this point that the
[48:48] master writes its own version number to
[48:55] disk after telling the primaries there's
[49:02] a bit of a problem here though because
[49:03] if the was that is there an ACK
[49:12] all right so maybe the master tells the
[49:17] primaries and backups and that their
[49:18] primaries and secondaries if they're a
[49:20] primary secondary tells him the new
[49:21] version number waits for the AK and then
[49:24] writes to disk or something unsatisfying
[49:27] about this I don't believe that works
[49:37] because of the possibility that the
[49:40] chunk servers with the most recent
### chunk 61 [49:40]
Lecture 3: GFS > Transcript

] because of the possibility that the
[49:40] chunk servers with the most recent[49:41] version numbers being offline at the
[49:44] time the master reboots we wouldn't want
[49:46] the master the master doesn't know the
[49:48] current version number it'll just accept
[49:50] whatever highest version number adheres
[49:51] which could be an old version number all
[49:54] right so this is a an area of my
[49:57] ignorance I don't really understand
[49:58] whether the master update system version
[50:00] number on this first and then tells the
[50:01] primary secondary or the other way
[50:03] around and I'm not sure it works either
[50:06] way okay but in any case one way or
[50:11] another the master update is version
[50:12] number tells the primary secondary look
[50:14] your primaries and secondaries here's a
[50:16] new version number and so now we have a
### chunk 62 [50:16]
Lecture 3: GFS > Transcript

imaries and secondaries here's a
[50:16] new version number and so now we have a[50:17] primary which is able to accept writes
[50:19] all right that's what the primaries job
[50:21] is to take rights from clients and
[50:23] organize applying those rights to the
[50:26] various chunk servers and you know the
[50:35] reason for the version number stuff is
[50:36] so that the master will recognize the
[50:44] which servers have this new you know the
[50:50] master hands out the ability to be
[50:52] primary for some chunk server we want to
[50:55] be able to recognize if the master
[50:58] crashes you know that it was that was
[51:01] the primary that only that primary and
[51:03] it secondaries which were actually
[51:05] processed which were in charge of
[51:06] updating that chunk that only those
[51:08] primaries and secondaries are allowed to
### chunk 63 [51:08]
Lecture 3: GFS > Transcript

ting that chunk that only those
[51:08] primaries and secondaries are allowed to[51:10] be chunk servers in the future and the
[51:12] way the master does this is with this
[51:14] version number logic
[51:17] okay so the master tells the primaries
[51:21] and secondaries that there it they're
[51:23] allowed to modify this block it also
[51:24] gives the primary a lease which
[51:27] basically tells the primary look you're
[51:29] allowed to be primary for the next sixty
[51:31] seconds after sixty Seconds you have to
[51:33] stop and this is part of the machinery
[51:37] for making sure that we don't end up
[51:39] with two primaries I'll talk about a bit
[51:41] later okay so now we were primary now
[51:46] the master tells the client who the
[51:50] primary and the secondary czar and at
[51:54] this point we're we're executing in
### chunk 64 [51:54]
Lecture 3: GFS > Transcript

rimary and the secondary czar and at
[51:54] this point we're we're executing in[51:59] figure two in the paper the client now
[52:02] knows who the primary secondaries are in
[52:04] some order or another and the paper
[52:05] explains a sort of clever way to manage
[52:08] this in some order or another the client
[52:10] sends a copy of the data it wants to be
[52:13] appended to the primary in all the
[52:15] secondaries and the primary in the
[52:18] secondaries write that data to a
[52:20] temporary location it's not appended to
[52:22] the file yet after they've all said yes
[52:24] we have the data the client sends a
[52:29] message to the primary saying look you
[52:31] know you and all the secondaries have
[52:33] the data I'd like to append it for this
[52:35] file
[52:36] the primary maybe is receiving these
[52:38] requests from lots of different clients
### chunk 65 [52:38]
Lecture 3: GFS > Transcript

primary maybe is receiving these
[52:38] requests from lots of different clients[52:40] concurrently it picks some order execute
[52:43] the client request one at a time and for
[52:45] each client a pen request the primary
[52:48] looks at the offset that's the end of
[52:50] the file the current end of the current
[52:53] chunk makes sure there's enough
[52:54] remaining space in the chunk and then
[52:56] tells then writes the clients record to
[52:59] the end of the current chunk and tells
[53:02] all the secondaries to also write the
[53:04] clients data to the end to the same
[53:08] offset the same offset in their chunks
[53:12] all right so the primary picks an offset
[53:20] all the replicas including the primary
[53:26] are told to write
[53:29] the new appended record at at offset the
[53:36] secondary's they may do it they may not
### chunk 66 [53:36]
Lecture 3: GFS > Transcript

appended record at at offset the
[53:36] secondary's they may do it they may not[53:38] do it I'm either run out of space maybe
[53:41] they crashed maybe the network message
[53:42] was lost from the primary so if a
[53:45] secondary actually wrote the data to its
[53:47] disk at that offset it will reply yes to
[53:50] the primary if the primary collects a
[53:52] yes answer from all of the secondaries
[53:58] so if they all of all of them managed to
[54:02] actually write and reply to the primary
[54:03] saying yes I did it then the primary is
[54:08] going to reply reply success to the
[54:10] client if the primary doesn't get an
[54:18] answer from one of the secondaries or
[54:21] the secondary reply sorry something bad
[54:23] happened I ran out of disk space my disk
[54:25] I don't know what then the primary
[54:28] replies no to the client and the paper
### chunk 67 [54:28]
Lecture 3: GFS > Transcript

 don't know what then the primary
[54:28] replies no to the client and the paper[54:37] says oh if the client gets an error like
[54:39] that back in the primary the client is
[54:42] supposed to reissue the entire append
[54:44] sequence starting again talking to the
[54:46] master to find out the most grease the
[54:48] chunk at the end of the file
[54:50] I want to know the client supposed to
[54:52] reissue the whole record append
[54:54] operation ah you would think but they
[55:01] don't so the question is jeez you know
[55:05] the the primary tells all the replicas
[55:08] to do the append yeah maybe some of them
[55:09] do some of them don't
[55:10] right if some of them don't then we
[55:12] apply an error to the client so the
[55:14] client thinks of the append in happen
[55:16] but those other replicas where the pen
### chunk 68 [55:16]
Lecture 3: GFS > Transcript

nt thinks of the append in happen
[55:16] but those other replicas where the pen[55:18] succeeded they did append so now we have
[55:23] replicas donor the same data one of them
[55:25] the one that returned in error didn't do
[55:27] the append and the ones they returned
[55:28] yes did do the append so that is just
[55:31] the way GFS works
[55:44] yeah so if a reader then reads this file
[55:47] they depending on what replica they be
[55:50] they may either see the appended record
[55:53] or they may not if the record append
[55:56] but if the record append succeeded if
[55:59] the client got a success message back
[56:00] then that means all of the replicas
[56:03] appended that record at the same offset
[56:05] if the client gets a no back then zero
[56:10] or more of the replicas may have
[56:14] appended the record of that all set and
### chunk 69 [56:14]
Lecture 3: GFS > Transcript

or more of the replicas may have
[56:14] appended the record of that all set and[56:15] the other ones not so the client got to
[56:20] know then that means that some replicas
[56:22] maybe some replicas have the record and
[56:25] some don't so what you which were
[56:27] roughly read from you know you may or
[56:29] may not see the record yeah
[56:39] oh that all the replicas are the same
[56:45] all the secondaries are the same version
[56:47] number so the version number only
[56:49] changes when the master assigns a new
[56:51] primary which would ordinarily happen
[56:53] and probably only happen if the primary
[56:55] failed so what we're talking about is is
[56:58] replicas that have the fresh version
[57:00] number all right and you can't tell from
[57:02] looking at them that they're missing
[57:03] that the replicas are different but
### chunk 70 [57:03]
Lecture 3: GFS > Transcript

looking at them that they're missing
[57:03] that the replicas are different but[57:08] maybe they're different and the
[57:09] justification for this is that yeah you
[57:11] know maybe the replicas don't all have
[57:13] that the appended record but that's the
[57:16] case in which the primary answer no to
[57:18] the clients and the client knows that
[57:20] the write failed and the reasoning
[57:22] behind this is that then the client
[57:24] library will reissue the append so the
[57:27] appended record will show up you know
[57:29] eventually the a pendel succeed you
[57:33] would think because the client I'll keep
[57:36] reissuing it until succeeds and then
[57:38] when it succeeds that means there's
[57:39] gonna be some offset you know farther on
[57:41] in the file where that record actually
[57:43] occurs in all the replicas as well as
### chunk 71 [57:43]
Lecture 3: GFS > Transcript

he file where that record actually
[57:43] occurs in all the replicas as well as[57:45] offsets preceding that word only occurs
[57:48] in a few of the replicas yes
[58:04] oh this is a great question
[58:11] the exact path that the right data takes
[58:15] might be quite important with respect to
[58:17] the underlying network and the paper
[58:19] somewhere says even though when the
[58:22] paper first talks about it he claims
[58:24] that the client sends the data to each
[58:26] replica in fact later on it changes the
[58:29] tune and says the client sends it to
[58:31] only the closest of the replicas and
[58:33] then the replicas then that replica
[58:36] forwards the data to another replica
[58:37] along I sort of chained until all the
[58:39] replicas had the data and that path of
[58:41] that chain is taken to sort of minimize
### chunk 72 [58:41]
Lecture 3: GFS > Transcript

as had the data and that path of
[58:41] that chain is taken to sort of minimize[58:43] crossing bottleneck inter switch links
[58:46] in a data center yes the version number
[59:00] only gets incremented if the master
[59:03] thinks there's no primary so it's a so
[59:06] in the ordinary sequence there already
[59:09] be a primary for that chunk the the
[59:13] the the master sort of will remember oh
[59:16] gosh there's already a primary and
[59:18] secondary for that chunk and it'll just
[59:19] it won't go through this master
[59:20] selection it won't increment the version
[59:22] number it'll just tell the client look
[59:24] up here's the primary with with no
[59:26] version number change
[59:42] my understanding is that if this is this
[59:47] I think you're asking a you're asking an
[59:49] interesting question so in this scenario
### chunk 73 [59:49]
Lecture 3: GFS > Transcript

ou're asking a you're asking an
[59:49] interesting question so in this scenario[59:51] in which the primaries isn't answered
[59:52] failure to the client you might think
[59:54] something must be wrong with something
[59:56] and that it should be fixed before you
[59:57] proceed in fact as far as I can tell the
[59:59] paper there's no immediate anything the
[01:00:03] client retries the append you know
[01:00:08] because maybe the problem was a network
[01:00:10] message got lost so there's nothing to
[01:00:11] repair right you know now we're gonna
[01:00:12] message got lost we should be
[01:00:13] transmitted and this is sort of a
[01:00:15] complicated way of retransmitting the
[01:00:17] network message maybe that's the most
[01:00:19] common kind of failure in that case just
[01:00:21] we don't change anything it's still the
### chunk 74 [01:00:21]
Lecture 3: GFS > Transcript

 of failure in that case just
[01:00:21] we don't change anything it's still the[01:00:22] same primary same secondaries the client
[01:00:26] we tries maybe this time it'll work
[01:00:28] because the network doesn't
[01:00:29] discard a message it's an interesting
[01:00:31] question though that if what went wrong
[01:00:32] here is that one of that there was a
[01:00:35] serious error or Fault in one of the
[01:00:37] secondaries what we would like is for
[01:00:41] the master to reconfigure that set of
[01:00:43] replicas to drop that secondary that's
[01:00:46] not working and it would then because
[01:00:49] it's choosing a new primary in executing
[01:00:50] this code path the master would then
[01:00:52] increment the version and then we have a
[01:00:54] new primary and new working secondaries
[01:00:56] with a new version and this not-so-great
### chunk 75 [01:00:56]
Lecture 3: GFS > Transcript

 and new working secondaries
[01:00:56] with a new version and this not-so-great[01:01:00] secondary with an old version and a
[01:01:02] stale copy of the data but because that
[01:01:04] has an old version the master will never
[01:01:07] never mistake it for being fresh but
[01:01:09] there's no evidence in the paper that
[01:01:10] that happens immediately as far as
[01:01:12] what's said in the paper the client just
[01:01:15] retries and hopes it works again later
[01:01:17] eventually the master will if the
[01:01:19] secondary is dead
[01:01:21] eventually the master does ping all the
[01:01:23] trunk servers will realize that and will
[01:01:25] probably then change the set of
[01:01:30] primaries and secondaries and increment
[01:01:32] the version but only only later
[01:01:40] the lease the leases that the answer to
### chunk 76 [01:01:40]
Lecture 3: GFS > Transcript

e version but only only later
[01:01:40] the lease the leases that the answer to[01:01:45] the question what if the master thinks
[01:01:49] the primary is dead because it can't
[01:01:52] reach it right that's supposing we're in
[01:01:53] a situation where at some point the
[01:01:55] master said you're the primary and the
[01:01:58] master was like painting them all the
[01:01:59] service periodically to see if they're
[01:02:01] alive because if they're dead and wants
[01:02:02] to pick a new primary the master sends
[01:02:05] some pings to you you're the primary and
[01:02:07] you don't respond right so you would
[01:02:09] think that at that point where gosh
[01:02:11] you're not responding to my pings then
[01:02:14] you might think the master at that point
[01:02:16] would designate a new primary it turns
[01:02:20] out that by itself is a mistake and the
### chunk 77 [01:02:20]
Lecture 3: GFS > Transcript

ignate a new primary it turns
[01:02:20] out that by itself is a mistake and the[01:02:23] reason for that the reason why it's a
[01:02:26] mistake to do that simple did you know
[01:02:30] use that simple design is that I may be
[01:02:32] pinging you and the reason why I'm not
[01:02:33] getting responses is because then
[01:02:35] there's something wrong with a network
[01:02:36] between me and you so there's a
[01:02:38] possibility that you're alive you're the
[01:02:39] primary you're alive I'm peeing you the
[01:02:41] network is dropping that packets but you
[01:02:42] can talk to other clients and you're
[01:02:44] serving requests from other clients you
[01:02:46] know and if I if I the master sort of
[01:02:49] designated a new primary for that chunk
[01:02:51] now we'd have two primaries processing
[01:02:54] rights but two different copies of the
### chunk 78 [01:02:54]
Lecture 3: GFS > Transcript

 have two primaries processing
[01:02:54] rights but two different copies of the[01:02:56] data and so now we have totally
[01:02:58] diverging copies the data and that's
[01:03:02] called that error having two primaries
[01:03:07] or whatever processing requests without
[01:03:10] knowing each other it's called squid
[01:03:12] brain and I'm writing this on board
[01:03:16] because it's an important idea and it'll
[01:03:19] come up again and it's caused or it's
[01:03:23] usually said to be caused by network
[01:03:24] partition that is some network error in
[01:03:33] which the master can't talk to the
[01:03:34] primary but the primary can talk to
[01:03:35] clients sort of partial network failure
[01:03:38] and you know these are some of the these
[01:03:41] are the hardest problems to deal with
[01:03:44] and building these kind of storage
### chunk 79 [01:03:44]
Lecture 3: GFS > Transcript

 the hardest problems to deal with
[01:03:44] and building these kind of storage[01:03:46] systems okay so that's the problem is we
[01:03:49] want to rule out the possibility of
[01:03:51] mistakingly designating too
[01:03:54] I'm Aries for the same chunk the way the
[01:03:56] master achieves that is that when it
[01:03:58] designates a primary it says it gives a
[01:04:00] primary Elyse which is basically the
[01:04:03] right to be primary until a certain time
[01:04:05] the master knows it remembers and knows
[01:04:08] how long the least lasts and the primary
[01:04:12] knows how long is least lasts if the
[01:04:14] lease expires the primary knows that it
[01:04:18] expires and will simply stop executing
[01:04:20] client requests it'll ignore or reject
[01:04:23] client requests after the lease expired
[01:04:24] and therefore if the master can't talk
### chunk 80 [01:04:24]
Lecture 3: GFS > Transcript

quests after the lease expired
[01:04:24] and therefore if the master can't talk[01:04:27] to the primary and the master would like
[01:04:29] to designate a new primary the master
[01:04:31] must wait for the lease to expire for
[01:04:33] the previous primary so that means
[01:04:35] master is going to sit on its hands for
[01:04:37] one lease period 60 seconds after that
[01:04:40] it's guaranteed the old primary will
[01:04:41] stop operating its primary and now the
[01:04:44] master can see if he doesn't need a new
[01:04:46] primary without producing this terrible
[01:04:50] split brain situation
[01:05:02] oh so the question is why is designated
[01:05:14] a new primary bad since the clients
[01:05:15] always ask the master first and so the
[01:05:18] master changes its mind then subsequent
[01:05:20] clients will direct the clients to the
### chunk 81 [01:05:20]
Lecture 3: GFS > Transcript

anges its mind then subsequent
[01:05:20] clients will direct the clients to the[01:05:22] new primary well one reason is that the
[01:05:26] clients cash for efficiency the clients
[01:05:28] cash the identity of the primary for at
[01:05:31] least for short periods of time even if
[01:05:34] they didn't though the bad sequence is
[01:05:37] that I'm the prime the master you ask me
[01:05:40] who the primary is I send you a message
[01:05:43] saying the primary is server one right
[01:05:46] and that message is inflate in the
[01:05:47] network and then I'm the master I you
[01:05:50] know I think somebody's failed whatever
[01:05:52] I think that primary is filled I
[01:05:53] designated a new primary and I send the
[01:05:55] primary message saying you're the
[01:05:56] primary and I start answering other
[01:05:57] clients who ask the primary is saying
### chunk 82 [01:05:57]
Lecture 3: GFS > Transcript

ary and I start answering other
[01:05:57] clients who ask the primary is saying[01:06:00] that that over there is the primary
[01:06:01] while the message to you is still in
[01:06:03] flight you receive the message saying
[01:06:04] the old primaries the primary you think
[01:06:07] gosh I just got this from the master I'm
[01:06:10] gonna go talk to that primary and
[01:06:11] without some much more clever scheme
[01:06:13] there's no way you could realize that
[01:06:14] even though you just got this
[01:06:16] information from the master it's already
[01:06:19] out of date and if that primary serves
[01:06:21] your modification requests now we have
[01:06:24] to and and respond success to you right
[01:06:27] then we have two conflicting replicas
[01:06:35] yes
[01:06:41] again you've a new file and no replicas
[01:06:50] okay so if you have a new file no
### chunk 83 [01:06:50]
Lecture 3: GFS > Transcript

n you've a new file and no replicas
[01:06:50] okay so if you have a new file no[01:06:53] replicas or even an existing file and no
[01:06:55] replicas the you'll take the path I drew
[01:06:58] on the blackboard the master will
[01:07:00] receive a request from a client saying
[01:07:02] oh I'd like to append to this file and
[01:07:04] then well I guess the master will first
[01:07:06] see there's no chunks associated with
[01:07:08] that file and it will just make up a new
[01:07:11] chunk identifier or perhaps by calling
[01:07:13] the random number generator and then
[01:07:15] it'll look in its chunk information
[01:07:17] table and see gosh I don't have any
[01:07:20] information about that chunk and it'll
[01:07:22] make up a new record saying but it must
[01:07:24] be special case code where it says well
[01:07:26] I don't know any version number this
### chunk 84 [01:07:26]
Lecture 3: GFS > Transcript

ial case code where it says well
[01:07:26] I don't know any version number this[01:07:28] chunk doesn't exist I'm just gonna make
[01:07:30] up a new version number one pick a
[01:07:32] random primary and set of secondaries
[01:07:35] and tell them look you are responsible
[01:07:37] for this new empty chunk please get to
[01:07:40] work the paper says three replicas per
[01:07:47] chunk by default so typically a primary
[01:07:50] and two backups
[01:08:03] okay okay so the maybe the most
[01:08:13] important thing here is just to repeat
[01:08:16] the discussion we had a few minutes ago
[01:08:21] the intentional construction of GFS we
[01:08:32] had these record a pens is that if we
[01:08:33] have three we have three replicas you
[01:08:41] know maybe a client sends in and a
[01:08:43] record a pen for record a and all three
### chunk 85 [01:08:43]
Lecture 3: GFS > Transcript

maybe a client sends in and a
[01:08:43] record a pen for record a and all three[01:08:46] replicas or the primary and both of the
[01:08:49] secondaries successfully append the data
[01:08:52] the chunks and maybe the first record in
[01:08:54] the trunk might be a in that case and
[01:08:55] they all agree because they all did it
[01:08:57] supposing another client comes in says
[01:09:00] look I want a pen record B but the
[01:09:03] message is lost to one of the replicas
[01:09:06] the network whatever supposably the
[01:09:08] message by mistake but the other two
[01:09:11] replicas get the message and one of
[01:09:13] them's a primary and my other
[01:09:14] secondaries they both depend of the file
[01:09:16] so now what we have is two the replicas
[01:09:19] that B and the other one doesn't have
[01:09:21] anything and then may be a third client
### chunk 86 [01:09:21]
Lecture 3: GFS > Transcript

nd the other one doesn't have
[01:09:21] anything and then may be a third client[01:09:26] wants to append C and maybe the remember
[01:09:29] that this is the primary the primary
[01:09:30] picks the offset since the primary just
[01:09:32] gonna tell the secondaries look in a
[01:09:35] right record C at this point in the
[01:09:38] chunk they all right C here now the
[01:09:43] client for be the rule for a client for
[01:09:45] B that for the client that gets us error
[01:09:47] back from its request is that it will
[01:09:50] resend the request so now the client
[01:09:53] that asked to append record B will ask
[01:09:56] again to a pen record B and this time
[01:09:57] maybe there's no network losses and all
[01:10:00] three replicas as a panel record be
[01:10:05] right and they're all lives there I'll
[01:10:07] have the most fresh version number and
### chunk 87 [01:10:07]
Lecture 3: GFS > Transcript

d they're all lives there I'll
[01:10:07] have the most fresh version number and[01:10:09] now if a client reads
[01:10:13] what they see depends on the track which
[01:10:17] replicas they look at it's gonna see in
[01:10:20] total all three of the records but it'll
[01:10:22] see in different orders depending on
[01:10:25] which replica reads it'll mean I'll see
[01:10:28] a B C and then a repeat of B so if it
[01:10:31] reads this replica it'll see B and then
[01:10:33] C if it reads this replica it'll see a
[01:10:36] and then a blank space in the file
[01:10:39] padding and then C and then B so if you
[01:10:41] read here you see C then B if you read
[01:10:44] here you see B and then C so different
[01:10:47] readers will see different results and
[01:10:49] maybe the worst situation is it some
[01:10:52] client gets an error back from the
### chunk 88 [01:10:52]
Lecture 3: GFS > Transcript

ybe the worst situation is it some
[01:10:52] client gets an error back from the[01:10:54] primary because one of the secondaries
[01:10:58] failed to do the append and then the
[01:11:00] client dies before we sending the
[01:11:02] request so then you might get a
[01:11:04] situation where you have record D
[01:11:07] showing up in some of the replicas and
[01:11:11] completely not showing up anywhere in
[01:11:13] the other replicas so you know under
[01:11:16] this scheme we have good properties for
[01:11:19] for appends that the primary sent back a
[01:11:23] successful answer for and sort of not so
[01:11:26] great properties for appends where the
[01:11:29] primary sent back of failure and the
[01:11:32] records the replicas just absolutely be
[01:11:35] different all different sets of replicas
[01:11:37] yes
[01:11:44] my reading in the paper is that the
### chunk 89 [01:11:37]
Lecture 3: GFS > Transcript

t sets of replicas
[01:11:37] yes
[01:11:44] my reading in the paper is that the[01:11:46] client starts at the very beginning of
[01:11:49] the process and asked the master again
[01:11:51] what's the last chunk in this file you
[01:11:54] know because it might be might have
[01:11:55] changed if other people are pending in
[01:11:56] the file yes
[01:12:17] so I can't you know I can't read the
[01:12:20] designers mind so the observation is the
[01:12:22] system could have been designed to keep
[01:12:24] the replicas in precise sync it's
[01:12:27] absolutely true and you will do it in
[01:12:30] labs 2 & 3 so you guys are going to
[01:12:33] design a system that does replication
[01:12:34] that actually keeps the replicas in sync
[01:12:36] and you'll learn you know there's some
[01:12:38] various techniques various things you
### chunk 90 [01:12:38]
Lecture 3: GFS > Transcript

'll learn you know there's some
[01:12:38] various techniques various things you[01:12:41] have to do in order to do that and one
[01:12:43] of them is that there just has to be
[01:12:46] this rule if you want the replicas to
[01:12:47] stay in sync it has to be this rule that
[01:12:50] you can't have these partial operations
[01:12:53] that are applied to only some and not
[01:12:54] others and that means that there has to
[01:12:56] be some mechanism to like where the
[01:12:58] system even if the client dies where the
[01:13:00] system says we don't wait a minute there
[01:13:01] was this operation I haven't finished it
[01:13:04] yet so you build systems in which the
[01:13:07] primary actually make sure the backups
[01:13:11] get every message
[01:13:29] if the first right abhi failed you think
[01:13:34] the sea should go with the beers
### chunk 91 [01:13:34]
Lecture 3: GFS > Transcript

he first right abhi failed you think
[01:13:34] the sea should go with the beers[01:13:37] well it doesn't you may think it should
[01:13:40] but the way the system actually operates
[01:13:42] is that the primary will add C to the
[01:13:46] end of the chunk and the after V yeah I
[01:13:57] mean one reason for this is that at the
[01:13:59] time the right Percy comes in the
[01:14:01] primary may not actually know what the
[01:14:03] fate of B was because we met multiple
[01:14:05] clients submitting a pen's concurrently
[01:14:07] and you know for high performance you
[01:14:10] want the primary to start the append for
[01:14:14] B first and then as soon as I can got
[01:14:17] the next stop set tell everybody did you
[01:14:20] see so that all this stuff happens in
[01:14:21] parallel you know by slowing it down you
### chunk 92 [01:14:21]
Lecture 3: GFS > Transcript

at all this stuff happens in
[01:14:21] parallel you know by slowing it down you[01:14:25] could you know the primary could sort of
[01:14:31] decide that B it totally failed and then
[01:14:33] send another round of messages saying
[01:14:35] please undo the right of B and there'll
[01:14:39] be more complex and slower I'm you know
[01:14:43] again the the justification for this is
[01:14:45] that the design is pretty simple it you
[01:14:48] know it reveals some odd things to
[01:14:53] applications and the hope was that
[01:14:58] applications could be relatively easily
[01:14:59] written to tolerate records being in
[01:15:01] different orders or who knows what or if
[01:15:04] they couldn't that applications could
[01:15:08] either make their own arrangements for
[01:15:11] picking an order themselves and writing
[01:15:13] you know sequence numbers in the files
### chunk 93 [01:15:13]
Lecture 3: GFS > Transcript

n order themselves and writing
[01:15:13] you know sequence numbers in the files[01:15:14] or something or you could just have a if
[01:15:17] application really was very sensitive to
[01:15:20] order you could just not have concurrent
[01:15:21] depends from different clients to the
[01:15:24] same file right you could just you know
[01:15:27] close files where order is very
[01:15:29] important like say it's a movie file you
[01:15:31] know you don't want to scramble
[01:15:32] bytes in a movie file you just write the
[01:15:35] Moot file you write the movie to the
[01:15:37] file by one client in sequential order
[01:15:40] and not with concurrent record depends
[01:15:49] okay all right
[01:15:56] the somebody asked basically what would
[01:16:04] it take to turn this design into one
[01:16:06] which actually provided strong
### chunk 94 [01:16:06]
Lecture 3: GFS > Transcript

] it take to turn this design into one
[01:16:06] which actually provided strong[01:16:08] consistency consistency closer to our
[01:16:11] sort of single server model where
[01:16:13] there's no surprises I don't actually
[01:16:18] know because you know that requires an
[01:16:20] entire new complex design it's not clear
[01:16:22] how to mutate GFS to be that design but
[01:16:24] I can list for you lists for you some
[01:16:26] things that you would want to think
[01:16:27] about if you wanted to upgrade GFS to a
[01:16:32] assistance did have strong consistency
[01:16:34] one is that you probably need the
[01:16:37] primary to detect duplicate requests so
[01:16:40] that when this second becomes in the
[01:16:43] primary is aware that oh actually you
[01:16:44] know we already saw that request earlier
[01:16:47] and did it or didn't do it and to try to
### chunk 95 [01:16:47]
Lecture 3: GFS > Transcript

ady saw that request earlier
[01:16:47] and did it or didn't do it and to try to[01:16:50] make sure that B doesn't show up twice
[01:16:52] in the file so one is you're gonna need
[01:16:54] duplicate detection another issues you
[01:16:59] probably if a secondary is acting a
[01:17:02] secondary you really need to design the
[01:17:05] system so that if the primary tells a
[01:17:06] secondary to do something
[01:17:08] the secondary actually does it and
[01:17:10] doesn't just return error right for a
[01:17:12] strictly consistent system having the
[01:17:15] secondaries be able to just sort of blow
[01:17:16] off primary requests with really no
[01:17:20] compensation is not okay so I think the
[01:17:24] secondaries have to accept requests and
[01:17:25] execute them or if a secondary has some
[01:17:28] sort of permanent damage like it's disk
### chunk 96 [01:17:28]
Lecture 3: GFS > Transcript

em or if a secondary has some
[01:17:28] sort of permanent damage like it's disk[01:17:30] got unplugged by mistake this you need
[01:17:32] to have a mechanism to like take the
[01:17:34] secondary out of the system so the
[01:17:36] primary can proceed with the remaining
[01:17:39] secondaries but GFS kind of doesn't
[01:17:41] either at least not right away
[01:17:45] and so that also means that when the
[01:17:49] primary asks secondary's to append
[01:17:50] something the secondaries have to be
[01:17:52] careful not to expose that data to
[01:17:54] readers until the primary is sure that
[01:17:57] all the secondaries really will be able
[01:17:59] to execute the append so you might need
[01:18:02] sort of multiple phases in the rights of
[01:18:05] first phase in which the primary asks
[01:18:06] the secondaries look you know I really
### chunk 97 [01:18:06]
Lecture 3: GFS > Transcript

hase in which the primary asks
[01:18:06] the secondaries look you know I really[01:18:09] like you to do this operation can you do
[01:18:11] it but don't don't actually do it yet
[01:18:13] and if all the secondaries answer with a
[01:18:15] promise to be able to do the operation
[01:18:17] only then the primary says alright
[01:18:20] everybody go ahead and do that operation
[01:18:22] you promised and people you know that's
[01:18:24] the way a lot of real world systems
[01:18:27] strong consistent systems work and that
[01:18:28] trick it's called two-phase commit
[01:18:32] another issue is that if the primary
[01:18:34] crashes there will have been some last
[01:18:38] set of operations that the primary had
[01:18:40] launched started to the secondaries but
[01:18:44] the primary crashed before it was sure
[01:18:46] whether those all the secondaries got
### chunk 98 [01:18:46]
Lecture 3: GFS > Transcript

mary crashed before it was sure
[01:18:46] whether those all the secondaries got[01:18:48] there copied the operation or not so if
[01:18:51] the primary crashes you know a new
[01:18:54] primary one of the secondaries is going
[01:18:56] to take over as primary but at that
[01:18:57] point the second the new primary and the
[01:19:01] remaining secondaries may differ in the
[01:19:03] last few operations because maybe some
[01:19:05] of them didn't get the message before
[01:19:07] the primary crashed and so the new
[01:19:09] primer has to start by explicitly
[01:19:11] resynchronizing with the secondaries to
[01:19:15] make sure that the sort of the tail of
[01:19:17] their operation histories are the same
[01:19:21] finally to deal with this problem of oh
[01:19:24] you know there may be times when the
[01:19:25] secondaries differ or the client may
### chunk 99 [01:19:25]
Lecture 3: GFS > Transcript

know there may be times when the
[01:19:25] secondaries differ or the client may[01:19:28] have a slightly stale indication from
[01:19:31] the master of which secondary to talk to
[01:19:33] the system either needs to send all
[01:19:35] client reads through the primary because
[01:19:38] only the primary is likely to know which
[01:19:41] operations have really happened or we
[01:19:43] need a least system for the secondaries
[01:19:45] just like we have for the primary so
[01:19:47] that it's well understood that when
[01:19:50] secondary Canon can't legally respond
[01:19:55] a client and so these are the things I'm
[01:19:56] aware of that would have to be fixed in
[01:19:58] this system tor added complexity and
[01:20:00] chitchat to make it have strong
[01:20:02] consistency and you're actually the way
[01:20:05] I got that list was by thinking about
### chunk 100 [01:20:05]
Lecture 3: GFS > Transcript

ncy and you're actually the way
[01:20:05] I got that list was by thinking about[01:20:08] the labs you're gonna end up doing all
[01:20:09] the things I just talked about as part
[01:20:12] of labs two and three to build a
[01:20:13] strictly consistent system okay so let
[01:20:18] me spend one minute on there's actually
[01:20:21] I have a link in the notes to a sort of
[01:20:23] retrospective interview about how well
[01:20:25] GFS played out over the first five or
[01:20:28] ten years of his life at Google so the
[01:20:32] high-level summary is that the most is
[01:20:36] that was tremendously successful and
[01:20:37] many many Google applications used it in
[01:20:40] a number of Google infrastructure was
[01:20:43] built as a late like big file for
[01:20:45] example BigTable I mean was built as a
[01:20:47] layer on top of GFS and MapReduce also
### chunk 101 [01:20:47]
Lecture 3: GFS > Transcript

BigTable I mean was built as a
[01:20:47] layer on top of GFS and MapReduce also[01:20:50] so widely used within Google may be the
[01:20:54] most serious limitation is that there
[01:20:57] was a single master and the master had
[01:20:59] to have a table entry for every file in
[01:21:01] every chunk and that men does the GFS
[01:21:04] use grew and they're about more and more
[01:21:06] files the master just ran out of memory
[01:21:08] ran out of RAM to store the files and
[01:21:11] you know you can put more RAM on but
[01:21:13] there's limits to how much RAM a single
[01:21:15] machine can have and so that was the
[01:21:18] most of the most immediate problem
[01:21:19] people ran into in addition the load on
[01:21:24] a single master from thousands of
[01:21:25] clients started to be too much in the
[01:21:28] master kernel they see if you can only
### chunk 102 [01:21:28]
Lecture 3: GFS > Transcript

 started to be too much in the
[01:21:28] master kernel they see if you can only[01:21:29] process however many hundreds of
[01:21:30] requests per second especially the right
[01:21:33] things to disk and pretty soon there got
[01:21:35] to be too many clients another problem
[01:21:39] with a some applications found it hard
[01:21:41] to deal with this kind of sort of odd
[01:21:44] semantics and a final problem is that
[01:21:47] the master that was not an automatic
[01:21:49] story for master failover
[01:21:52] in the original in the GFS paper as we
[01:21:54] read it like required human intervention
[01:21:56] to deal with a master that had sort of
[01:21:59] permanently crashed and needs to be
[01:22:00] replaced and that could take tens of
[01:22:03] minutes or more I was just too long for
[01:22:05] failure recovery for some applications
### chunk 103 [01:22:05]
Lecture 3: GFS > Transcript

r more I was just too long for
[01:22:05] failure recovery for some applications[01:22:09] okay excellent I'll see you on Thursday
[01:22:13] and we'll hear more about all these
[01:22:15] themes over the semester
