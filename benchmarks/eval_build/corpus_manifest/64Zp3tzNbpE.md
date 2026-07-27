# Lecture 6: Fault Tolerance: Raft (1)
- video_id: 64Zp3tzNbpE
- document_id: c72da92dfc8e4375bd056c5ad82423c0
- platform: youtube
- duration: 4800s (80m00s)
- chunk_count: 101
- language_guess: en

## L3 brief
This text summarizes a lecture on the Raft consensus algorithm, detailing how majority voting, leader elections, and log replication enable fault-tolerant distributed systems while preventing split-brain scenarios.

## L2 summary
This transcript covers the design of fault-tolerant replicated systems using the Raft consensus algorithm to maintain consistency and prevent split-brain scenarios. It details how distributed systems use majority voting (quorum systems requiring $2F + 1$ servers to tolerate $F$ failures) as an improvement over single points of failure like MapReduce or GFS. The text outlines Raft's technical implementation, including log replication via `AppendEntries` RPCs, term numbers, election timers, and randomized timeouts to handle network partitions and prevent split votes. Furthermore, it addresses edge cases such as leader crashes, log divergence, reboot recovery, and the necessity of treating potentially committed entries as permanent to guarantee overall system correctness.

## Chunks
### chunk 0 [00:00]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

[00:00] all right well let's get started
[00:06] today and indeed today and tomorrow I'm
[00:10] gonna talk about raft both because I
[00:14] hope it'll be helpful you for you in
[00:16] implanting though the labs and also
[00:19] because you know it's just a case study
[00:21] in the details of how to get state
[00:23] machine replication correct so we have
[00:28] introduction to the problem you may have
[00:31] noticed a pattern in fault-tolerant
[00:33] systems that we've looked at so far
[00:35] one is that MapReduce replicates
[00:40] computation but the replication is
[00:43] controlled the whole computation is
[00:45] controlled by a single master another
[00:50] example I'd like to draw your attention
[00:52] to is that GFS replicates data right as
### chunk 1 [00:52]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

 I'd like to draw your attention
[00:52] to is that GFS replicates data right as[00:55] this primary backup scheme for
[00:56] replicating the actual contents of files
[00:58] but it relies on a single master to
[01:01] choose who the primary is for every
[01:03] piece of data another example vmware ft
[01:07] replicates computational write on a
[01:09] primary virtual machine and a backup
[01:11] virtual machine but in order to figure
[01:14] out what to do next if one of them seems
[01:16] to a fail it relies on a single test and
[01:19] set server to help the choose to help it
[01:22] ensure that exactly one of the primary
[01:23] of the backup takes over if there's some
[01:26] kind of failure so in all three of these
[01:29] cases sure there was a replication
[01:31] system but sort of tucked away in a
[01:34] corner in the replication system there
### chunk 2 [01:34]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

stem but sort of tucked away in a
[01:34] corner in the replication system there[01:36] was some scheme where a single entity
[01:37] was required to make a critical decision
[01:40] about who the primary was in the cases
[01:43] we care about so a very nice thing about
[01:47] having a single entity decide who's
[01:50] gonna be the primary is that it can't
[01:53] disagree with itself right there's only
[01:55] one of it makes some decision that's the
[01:57] decision it made but the bad thing about
[02:00] having a single entity decide like who
[02:03] the primary is is that it itself as a
[02:04] single point of failure and so you can
[02:06] view these systems that we've looked at
[02:08] it sort of pushing the real heart of the
[02:11] fault tolerance
[02:13] Machinery into a little corner that is
[02:16] the single entity that decides who's
### chunk 3 [02:16]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

hinery into a little corner that is
[02:16] the single entity that decides who's[02:18] going to be the primary if there's a
[02:20] failure now this whole thing is about
[02:23] how to avoid split brain the reason why
[02:25] we have to have have to be extremely
[02:27] careful about making the decision about
[02:29] who should be the primary if there's a
[02:31] failure is that otherwise we risks split
[02:33] brain and just make this point super
[02:38] clear I'm gonna just remind you what the
[02:45] problem is and why it's a serious
[02:47] problem so supposing for example where
[02:49] we want to build ourselves a replicated
[02:52] test and set server that is we're
[02:54] worried about the fact that vmware ft
[02:56] relies on this test and set server to
[02:58] choose who the primary is so let's build
[03:00] a replicated testing set server i'm
### chunk 4 [03:00]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

se who the primary is so let's build
[03:00] a replicated testing set server i'm[03:02] gonna do this it's gonna be broken it's
[03:04] just an illustration for why why it's
[03:08] difficult to get this but brain problem
[03:10] correctly so you know we're gonna
[03:12] imagine we have a network and maybe two
[03:16] servers which are supposed to be
[03:18] replicas of our test and set service
[03:21] connected and you know maybe two clients
[03:23] they need to know who's the primary
[03:24] right now or actually maybe these
[03:26] clients in this case are the primary in
[03:28] the back up in vmware ft so if it's a
[03:34] test and set service then you know both
[03:36] these databases mostly servers start out
[03:38] with their state that is the state of
[03:40] this test flight back in zero and the
[03:42] one operation their clients can send is
### chunk 5 [03:42]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

test flight back in zero and the
[03:42] one operation their clients can send is[03:44] the test and set operation which is
[03:46] supposed to set the flag of the
[03:50] replicated service to one so i should
[03:52] set both copies and then return the old
[03:55] value so it's essentially acts as a kind
[03:57] of simplified lock server okay so the
[04:02] problem situation the lowly worried
[04:05] about split-brain arises when a client
[04:08] can talk to one of the servers but can't
[04:11] talk to the other so we're imagining
[04:12] either that when clients send a request
[04:14] they send it to both I'm just gonna
[04:17] assume that now and almost doesn't
[04:19] matter so let's assume that the protocol
[04:20] is that the clients supposed to send
[04:22] ordinarily any request to both servers
[04:24] and somehow we you know we need
### chunk 6 [04:24]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

] ordinarily any request to both servers
[04:24] and somehow we you know we need[04:27] think through what the clients should do
[04:29] if one of the server's doesn't respond
[04:31] right or what the system should do if
[04:33] one of the server seems to gotten
[04:34] responsive so let's imagine now the
[04:38] client one can contact server one but
[04:40] not server two how should the system
[04:42] react one possibility is for is that we
[04:46] think well you know gosh we certainly
[04:48] don't want to just talk to client to
[04:49] server one because that would leave the
[04:50] second replica inconsistent if we set
[04:53] this value to one but didn't also set
[04:54] this value to one
[04:55] so maybe the rule should be that the
[04:57] client is always required to talk to
[04:59] both replicas to both servers for any
### chunk 7 [04:59]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

ient is always required to talk to
[04:59] both replicas to both servers for any[05:01] operation and shouldn't be allowed to
[05:03] just talk to one of them so why is that
[05:05] the wrong answer so the rule is o in our
[05:10] replicated system the clients always
[05:12] require to talk to both replicas in
[05:15] order to make progress at all in fact
[05:22] it's worse it's worse than talking to a
[05:25] single server because now the system has
[05:27] a problem if either of these servers is
[05:30] crashed or or you can't talk to it at
[05:33] least with a non replicated service
[05:34] you're only depending on one server but
[05:36] here we am both servers have to be a lot
[05:37] if we require the client to talk to both
[05:40] servers then both servers has to be live
[05:41] so we can't possibly require the client
[05:43] to actually you know wait for both
### chunk 8 [05:43]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

 we can't possibly require the client
[05:43] to actually you know wait for both[05:46] servers to respond if we don't have
[05:49] fault tolerance we need it to be able to
[05:50] proceed so another obvious answer is
[05:52] that if the client can't talk to both
[05:55] well it just talks to the one who can
[05:56] talk to and figures the other ones dead
[05:59] so what's up why is that also not the
[06:02] right answer
[06:08] the troubling scenario is if the other
[06:10] server is actually alive so suppose the
[06:12] actual problem or encountering is not
[06:13] that this server crashed which would be
[06:16] good for us but the much worse issue
[06:20] that something went wrong with the
[06:21] network cable and that this client can
[06:23] talk to climb one can talk to server one
[06:26] but not server two and there's maybe
### chunk 9 [06:26]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

to climb one can talk to server one
[06:26] but not server two and there's maybe[06:27] some other client out there that conduct
[06:29] a server two but not server one so if we
[06:33] make the rule that if a client can talk
[06:35] to both servers that it's okay in order
[06:38] to be fault tolerant that I just talked
[06:39] to one then what's just inevitably gonna
[06:43] happen said this cable is gonna break
[06:46] thus cutting the network in half client
[06:48] one is gonna send a test and set request
[06:51] to server one server one will you know
[06:53] set it state to one and return the
[06:56] previous value of zero to client one and
[06:58] so that mean client mom will think it
[06:59] has the lock and if it's a VMware ft
[07:02] server will think it can be takeovers
[07:04] primarily but this replica still of zero
### chunk 10 [07:04]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

 will think it can be takeovers
[07:04] primarily but this replica still of zero[07:06] in it all right so now if client to
[07:08] who've also sends a test and set request
[07:10] to you know what price to send them to
[07:12] both sees that server one appears to be
[07:14] down follows the rule that says well you
[07:16] just send to the one server but you can
[07:17] talk to then it will also think that it
[07:22] would either quiet because client you
[07:23] also think that it acquired the lock and
[07:25] so now you know if we were imagining
[07:27] this test and that server was going to
[07:28] be used with the and where ft we have
[07:29] not both replicas both of these VMware
[07:35] machines I think they could be primary
[07:37] by themselves without consulting the
[07:41] other server so that's a complete
[07:42] failure so with this set up and two
### chunk 11 [07:42]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

1] other server so that's a complete
[07:42] failure so with this set up and two[07:45] servers it seemed like we had this we
[07:47] just had to choose either you wait for
[07:49] both and you're not fault-tolerant or
[07:52] you wait for just one and you're not
[07:54] correct and then our correct version
[07:57] it's often called split brain so
[07:59] everybody see this well
[08:09] so this was basically where things stood
[08:12] until the late 80s and when people but
[08:16] people did want to build replicated
[08:18] systems you know like the computers that
[08:20] control telephone switches or the
[08:22] computers that ran banks you know there
[08:24] was placer when we spend a huge amount
[08:26] of money in order to have reliable
[08:27] service and so they would replicate they
[08:29] would build replicated systems and the
### chunk 12 [08:29]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

 and so they would replicate they
[08:29] would build replicated systems and the[08:31] way they would deal then way would that
[08:33] they would have replication but try to
[08:35] rule out of rule out split brain it's a
[08:38] couple of techniques one is they would
[08:41] build a network that could not fail and
[08:45] so usually what that means and in fact
[08:47] you guys use networks that essentially
[08:49] cannot fail all the time the wires
[08:51] inside your laptop you know connecting
[08:53] the CPU to the DRAM are effectively what
[08:57] you know a network that cannot fail
[08:59] between the between your CPU and DRAM so
[09:02] you know with reasonable assumptions and
[09:05] lots of money and you know sort of
[09:07] carefully controlled physical situation
[09:10] like you don't want to have a cable
[09:11] snaking across the floor that somebody
### chunk 13 [09:11]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

ke you don't want to have a cable
[09:11] snaking across the floor that somebody[09:12] can step on you know it's got to be
[09:15] physically designed set up with a
[09:17] network that cannot fail you can rule
[09:19] out split brain it's bit of an
[09:21] assumption but with enough money people
[09:22] get quite close to this because if the
[09:25] network cannot fail that basically means
[09:27] that the client can't talk to a server
[09:28] to that means server two must be down
[09:31] because it can't have been the network
[09:33] malfunctioning so that was one way that
[09:35] people sort of built replication systems
[09:38] it didn't suffer from split brain
[09:42] another possibility would be to have
[09:44] some human beings sort out the problem
[09:46] that is don't automatically do anything
[09:48] instead have the clients you know by
### chunk 14 [09:48]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

 is don't automatically do anything
[09:48] instead have the clients you know by[09:49] default clients always have to wait for
[09:51] you know both replicas to respond or
[09:54] something never allowed to proceed with
[09:56] just one of them but you can you know
[09:58] call somebody's beeper to go off some
[10:00] human being goes to the machine room and
[10:02] sort of looks at the two replicas and
[10:04] either turns one off to make sure it's
[10:07] definitely dead
[10:07] or verifies that one of them has indeed
[10:10] crashed and if the other is alive and so
[10:13] you're essentially using the human as a
[10:14] as the tie breaker and the human is a
[10:17] you know if they were a computer it
[10:20] would be a single point if you
[10:21] themselves so for a long time people use
[10:25] one of the other these schemes in order
### chunk 15 [10:25]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

es so for a long time people use
[10:25] one of the other these schemes in order[10:27] to build replicated systems and it's not
[10:28] you know they can be made to work the
[10:31] humans don't respond very quickly and
[10:32] the network that cannot fail is
[10:34] expensive but it's not not doable but it
[10:38] turned out that you can actually build
[10:42] automated failover systems that can work
[10:45] correctly in the face of flaky networks
[10:48] of networks that could fail on the can
[10:51] partition so this split of the network
[10:53] in half where the two sides operate they
[10:54] can't talk to each other that's usually
[10:56] called a partition and the big insight
[11:04] that people came up with in order to
[11:06] build automated replication systems that
[11:10] don't suffer from split brain is the
[11:12] idea of a majority vote this is a
### chunk 16 [11:12]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

] don't suffer from split brain is the
[11:12] idea of a majority vote this is a[11:20] concept that shows up in like every
[11:22] other sentence practically in the raft
[11:24] paper sort of fundamental way of
[11:28] proceeding the first step is to have an
[11:31] odd number of servers instead of an even
[11:33] number of servers like one flaw here is
[11:35] that it's a little bit too symmetric all
[11:37] right the two sides of the split here
[11:39] just they just look the same so they run
[11:41] the same software they're gonna do the
[11:42] same thing and that's not good but if
[11:44] you have an odd number of servers then
[11:47] it's not symmetric anymore right at
[11:50] least a single network split will be
[11:52] presumably two servers on one side and
[11:54] one server on the other side and they
[11:56] won't be symmetric at all and that's
### chunk 17 [11:56]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

e server on the other side and they
[11:56] won't be symmetric at all and that's[11:58] part of what majority vote majority
[12:00] voting schemes are appealing to so basic
[12:04] ideas you have an odd number of servers
[12:05] in order to make progress of any kind so
[12:08] in raft elect a leader or cause a log
[12:10] entry to be committed in order to make
[12:12] any progress at each step you have to
[12:15] assemble a majority of the server's more
[12:18] than half more than half of all the
[12:20] servers in order to sort of approve that
[12:22] step like vote for a meet or accept a
[12:25] new log entry and commit it so you know
[12:29] the most straightforward way is that two
[12:32] or three servers required to do anything
[12:37] one reason this works of course is that
[12:40] if there's a partition there can't be
### chunk 18 [12:40]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

eason this works of course is that
[12:40] if there's a partition there can't be[12:43] more than one partition with a majority
[12:45] of the server's in it that's one way to
[12:47] look at this a partition can have one
[12:51] server in it which it's not a majority
[12:53] or maybe you can have two but if one
[12:55] partition has two then the other
[12:56] partition has to have only one server in
[12:58] it and therefore will never be able to
[13:00] assemble a majority and won't be able to
[13:02] make progress and just to be totally
[13:07] clear when we're talking about a
[13:09] majority it's always a majority out of
[13:11] all of the server's not just a live
[13:14] servers this is the point that confused
[13:15] me for a long time but if you have a
[13:17] system with three servers and maybe some
[13:19] of them have failed or something if you
### chunk 19 [13:19]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

ith three servers and maybe some
[13:19] of them have failed or something if you[13:20] need to assemble in the majority it's
[13:22] always two out of three even if you know
[13:24] that one has failed the majority is
[13:26] always out of the total number of
[13:27] servers there's a more general
[13:30] formulation of this because a majority
[13:33] voting system in which two out of three
[13:35] are required to make progress it can
[13:37] survive the failure of one server right
[13:40] any two servers are enough to make
[13:42] progress if you need to be able to if
[13:45] you're you know you worried about how
[13:46] reliable your servers are or then you
[13:49] can build systems that have more servers
[13:51] and so the more general formulation is
[13:53] if you have two F + 1 servers then you
[13:59] can withstand you know so if it's three
### chunk 20 [13:59]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

 have two F + 1 servers then you
[13:59] can withstand you know so if it's three[14:06] that means F is one and the system with
[14:09] three servers you can tolerate F servers
[14:12] step one failure and still keep going
[14:19] all right often these are called quorum
[14:22] systems because the two out of three is
[14:25] sometimes held a quorum okay so one
[14:29] property I've already mentioned about
[14:30] these majority voting systems is that at
[14:34] most one partition can have a majority
[14:36] and therefore if the networks
[14:38] partitioned we can't have both halves of
[14:40] the network making progress another more
[14:42] subtle thing that's going on here is
[14:44] that if you always need a majority of
[14:48] the servers to proceed and you go
[14:52] through a sort of succession of
[14:54] operations in which reach operations
### chunk 21 [14:54]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

52] through a sort of succession of
[14:54] operations in which reach operations[14:55] somebody assembled a majority like you
[14:58] know votes for leaders or let's say
[15:00] votes for leaders arrived then at every
[15:04] step the majority you assemble for that
[15:06] step must contain at least one server
[15:09] that was in the previous majority that
[15:11] is any two majorities overlap in at
[15:13] least one server and it's really that
[15:17] property more than anything else that
[15:21] raft is relying on to avoid split brain
[15:25] it's the fact that for example when you
[15:27] have a leader a successful leader
[15:28] election and leader assembles votes from
[15:30] a majority its majority is guaranteed to
[15:32] overlap with the previous leaders
[15:34] majority and so for example the new
[15:36] leader is guaranteed to know about the
### chunk 22 [15:36]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

jority and so for example the new
[15:36] leader is guaranteed to know about the[15:39] term number used by the previous leader
[15:41] because it's a majority overlaps with
[15:43] the previous leaders majority and
[15:45] everybody in the previous leaders
[15:47] majority knew about the previous leaders
[15:49] term number
[15:50] similarly anything the previous leader
[15:53] could have committed must be present in
[15:55] a majority of the servers in raft and
[15:57] therefore any new leaders majority must
[15:59] overlap at at least one server with
[16:01] every committed entry from the previous
[16:04] leader this is a big part of why it is
[16:08] that wrapped is correct
[16:14] any questions about the general concept
[16:18] of majority voting systems
[16:27] these muscle ad servers
[16:31] it's possible intersection something
### chunk 23 [16:27]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

ems
[16:27] these muscle ad servers
[16:31] it's possible intersection something[16:34] maybe six in the paper explains how to
[16:36] add it or change the set of servers and
[16:41] it's possible you need to do it in a
[16:44] long-running system if you're running
[16:45] your system for five ten years you know
[16:48] you're gonna need to replace the servers
[16:50] after a while you know one of them fails
[16:52] permanently or you upgrade or you move
[16:55] machine rooms to a different machine
[16:56] room you really do need to be able to
[16:58] support changing sets of servers so
[17:00] that's a it certainly doesn't happen
[17:01] every day but it's a critical part of
[17:03] this or a long-term maintainability of
[17:05] these systems and you know the RAF
[17:08] authors sort of pat themselves on the
[17:10] back that they have a scheme that deals
### chunk 24 [17:10]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

rs sort of pat themselves on the
[17:10] back that they have a scheme that deals[17:13] with this which as well they might
[17:14] because it's complex all right so using
[17:21] this idea in about 1990 or so there were
[17:25] two systems proposed at about the same
[17:28] time that realized that you could use
[17:31] this majority voting system to kind of
[17:34] get around the apparent impossibility of
[17:38] avoiding split brain by using basically
[17:41] by using three servers instead of two
[17:43] and taking majority votes and in one of
[17:46] these very early systems was called
[17:48] Paxos the RAF paper talks about this a
[17:51] lot and another of these very early
[17:54] systems was called view stamp
[17:56] replication a previa des vs r4 view
[18:00] stamp replication and even though Paxos
[18:02] pod is by far the more widely known
### chunk 25 [18:02]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

mp replication and even though Paxos
[18:02] pod is by far the more widely known[18:05] system in this department raft is
[18:07] actually closer to design in design to
[18:09] view statment few stamp application
[18:11] which was invented by people at MIT and
[18:16] so there's a sort of a law many decade
[18:19] history of these systems and they only
[18:21] really came to the forefront and started
[18:24] being used a lot in deployed big
[18:27] distributed sisty systems about 15 years
[18:29] ago a good 15 years after they were
[18:31] originally invented okay so let me talk
[18:39] about Rath now
[18:42] raft is a takes the form of a library
[18:46] intended to be included in some service
[18:49] application so if you have a replicated
[18:51] service that each of the replicas in the
[18:53] service is gonna be some application
### chunk 26 [18:53]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

ce that each of the replicas in the
[18:53] service is gonna be some application[18:55] code which you know receives rpcs or
[18:57] something plus a raft library and the
[19:00] raft libraries cooperate with each other
[19:01] to mean replication maintain replication
[19:06] so sort of software overview of a single
[19:10] raft replica is that at the top we can
[19:13] think of the replicas having the
[19:15] application code so it might be for lab
[19:17] 3 a key-value server so maybe we have
[19:20] some key value server and in a state the
[19:24] application has state that raft is
[19:26] helping it manage replicated state and
[19:28] for a key value server it's going to be
[19:30] a table of keys and values the next
[19:39] layer down is a raft layer so the key
[19:44] value server is gonna sort of make
[19:45] function calls into raft and they're
### chunk 27 [19:45]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

 value server is gonna sort of make
[19:45] function calls into raft and they're[19:47] gonna chitchat back and forth a little
[19:49] bit and raft keeps a little bit of state
[19:52] you can see it in Figure 2 and for our
[19:54] purposes really the most critical piece
[19:56] of state is that raft has a log of
[19:59] operations and a system with 3 breath
[20:08] will cause we're actually gonna have you
[20:09] know 3 servers that have exactly the
[20:12] same identical structure and hopefully
[20:14] the very same data sitting in sitting at
[20:19] both layers
[20:32] right outside of this there's gonna be
[20:35] clients and the game is that so we have
[20:38] you know client 1 and client two whole
[20:40] bunch of clients the clients don't
[20:42] really know the clients are you know
[20:44] just external code that needs to be able
### chunk 28 [20:44]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

y know the clients are you know
[20:44] just external code that needs to be able[20:46] to use the service and the hope is the
[20:49] clients won't really need to be aware
[20:50] that they're talking to a replicated
[20:52] service that to the clients that are
[20:53] looking almost like it's just one server
[20:55] and they talked with one server and so
[20:59] the clients actually send client
[21:00] requests to the key to the application
[21:04] layer of the current leader the replica
[21:08] that's the current leader in raft and so
[21:11] these are gonna be you know application
[21:13] level requests for a database for a key
[21:15] value server these might be put in get
[21:17] requests you know put takes a key and a
[21:20] value and updates the table and get
[21:26] asked the service to get the current key
[21:29] current value corresponding to some key
### chunk 29 [21:29]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

e service to get the current key
[21:29] current value corresponding to some key[21:34] so this like has nothing about to do
[21:36] with raft it's just sort of
[21:37] client-server interaction for whatever
[21:38] service we're building but once one of
[21:41] these commands gets sent from the
[21:43] requests get sent from the clients of
[21:44] the server what actually happens is you
[21:48] know on a non replicated server the
[21:50] application code would like execute this
[21:53] request and say update the table and
[21:54] response to a book but not in a raft
[21:56] replicated service instead if assuming
[21:59] the client sends a request to leader
[22:00] what really happens is the application
[22:04] layer simply sends the request the
[22:06] clients request down into the raft layer
[22:08] to say look you know here's a request
### chunk 30 [22:08]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

s request down into the raft layer
[22:08] to say look you know here's a request[22:09] please get it committed into the
[22:13] replicated log and tell me when you're
[22:15] done and so at this point the rafts
[22:17] chitchat with each other until all the
[22:23] replicas are a majority the replicas get
[22:25] this new operation into their logs said
[22:29] it is replicated and then when its
[22:31] leader knows that all of the replicas of
[22:34] a copy of this only then as a raft sent
[22:38] a notification up back up to the key
[22:40] value they are saying aha that operation
[22:42] you sent me I mean
[22:44] it's been now committed into all the
[22:46] replicas and so it's safely replicated
[22:49] and at this point it's okay to execute
[22:51] that operation a raft you know the
[22:55] client sends a request with the key
### chunk 31 [22:55]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

] that operation a raft you know the
[22:55] client sends a request with the key[22:57] value layer Q value layer does not
[22:59] execute it yet so we're not sure because
[23:01] it hasn't been replicated only when it's
[23:04] in out and the logs of all the replicas
[23:09] then raft notifies the leader now the
[23:11] leader actually execute the operation
[23:13] which corresponds to you know for a put
[23:15] updating the value yet reading correct
[23:20] value out of the table and then finally
[23:22] sends the reply back to the client so
[23:26] that's the ordinary operation of it
[23:34] submitted if it's in a majority and
[23:36] again the reason why I can't be all is
[23:38] that if we want to build a
[23:39] fault-tolerant system it has to be able
[23:41] to make progress even if some of the
[23:43] server's have failed so yeah so ever
### chunk 32 [23:43]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

o make progress even if some of the
[23:43] server's have failed so yeah so ever[23:49] it's committed when it's in a majority
[23:54] [Music]
[24:08] yeah and so in addition when operations
[24:12] finally committed each of the replicas
[24:14] sends the operation up each of the raft
[24:17] library layer sends the operation up to
[24:20] the local application layer in the local
[24:22] application layer applies that operation
[24:24] to its state its state and so they all
[24:27] so hopefully all the replicas seem the
[24:29] same stream of operations they show up
[24:32] in these up calls in the same order they
[24:34] get applied to the state in the same
[24:36] order and you know assuming the
[24:38] operations are deterministic which they
[24:41] better be the state of the replicas
[24:45] replicated State will evolve in
### chunk 33 [24:45]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

:41] better be the state of the replicas
[24:45] replicated State will evolve in[24:48] identically on all the replicas so
[24:50] typically this this table is what the
[24:52] paper is talking about when it talks
[24:55] about state a different way of viewing
[25:02] this interaction and one that'll sort of
[25:05] notation that will come up a lot in this
[25:07] course is that a sort of time diagram
[25:10] I'll draw you a time diagram of how the
[25:11] messages work so let's imagine we have a
[25:13] client and server one is the leader that
[25:18] we also have server to server three and
[25:23] time flows downward on this diagram we
[25:25] imagine the client sending the original
[25:27] request to server one after that server
[25:31] ones raft layer sends an append entries
[25:35] RPC to each of the two replicas this is
### chunk 34 [25:35]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

ft layer sends an append entries
[25:35] RPC to each of the two replicas this is[25:42] just an ordinary I'll say a put request
[25:44] this is append entries requests the
[25:49] server is now waiting for replies and
[25:51] the server's from other replicas as soon
[25:55] as replies from a majority arrive back
[25:58] including the leader itself so in a
[26:00] system with only three about because the
[26:02] leader only has to wait for one other
[26:03] replica to respond positively to an
[26:06] append entries as soon as it assembles
[26:09] positive responses from a majority the
[26:14] leader
[26:15] execute a command figures out what the
[26:18] answer is like forget
[26:20] and sends the reply back to the client
[26:25] I mean why of course you know if s who's
[26:27] actually awry alive it'll send back its
[26:30] response too but we're not waiting for
### chunk 35 [26:30]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

ly awry alive it'll send back its
[26:30] response too but we're not waiting for[26:32] it although it's useful to know and
[26:35] figure - all right everybody see this
[26:40] this is the sort of ordinary operation
[26:43] of the system no no failures
[26:51] oh gosh yeah I like I left out important
[26:55] steps so you know this point the leader
[26:57] knows oh I got you know I'm adora t have
[26:59] put it in no log I can go ahead and
[27:01] execute it and reply yes to the client
[27:03] because it's committed but server two
[27:05] doesn't know anything yet it just knows
[27:06] well you know I got this request from
[27:07] the leader but I don't know if it's
[27:09] committed yet depends on for example
[27:11] whether my reply got back to the leader
[27:13] for all server to knows it's reply was
[27:15] brought by the network maybe the leader
### chunk 36 [27:15]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

l server to knows it's reply was
[27:15] brought by the network maybe the leader[27:16] never heard the reply and never decided
[27:18] to commit this request so there's
[27:20] actually another stage once the server
[27:24] realizes that a request is committed it
[27:28] then needs to tell the other replicas
[27:31] that fact and so there are there's
[27:38] there's an extra message here exactly
[27:40] what that message is depends a little
[27:42] bit on what what else is going on it's
[27:45] at least in raft there's not an explicit
[27:49] commit message instead the information
[27:51] is piggybacked inside the next append
[27:53] entries that leader sends out the next
[27:55] append entries RPC it sends out for
[27:57] whatever reason like there's a commit
[28:00] meter commit or something filled in that
[28:01] RPC and the next time the leader needs
### chunk 37 [28:01]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

ommit or something filled in that
[28:01] RPC and the next time the leader needs[28:05] have to send a heartbeat heartbeat or
[28:07] needs to send out a new client request
[28:10] because some different client requests
[28:13] or something it'll send out the new hire
[28:16] leader commit value and at that point
[28:19] the replicas will execute the operation
[28:25] and apply it to their state yes
[28:39] oh yes so this is a this is a protocol
[28:43] that has a quite a bit of chitchat in it
[28:45] and it's not super fast indeed you know
[28:51] yeah client sends in request request has
[28:53] to get to the server the server talks to
[28:54] at least you know another instance that
[28:57] multiple messages has to wait for the
[28:58] responses send something back so there's
[29:00] a bunch of message round-trip times kind
[29:02] of embedded here
### chunk 38 [29:00]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

here's
[29:00] a bunch of message round-trip times kind
[29:02] of embedded here[29:10] yes if so this is up to you as the
[29:15] implementer actually exactly when the
[29:17] leader sends out the updated commit
[29:21] index if client requests a comeback only
[29:26] very occasionally then you know the
[29:29] leader may want to send out a heartbeat
[29:30] or send out a special append entries
[29:33] message if client requests come quite
[29:37] frequently then it doesn't matter
[29:38] because if they come you know there's
[29:40] thousand arrive per second and gee so
[29:42] it'll be another one along very soon and
[29:43] so you can piggyback so without
[29:45] generating an extra message which is
[29:46] somewhat expensive you can get the
[29:48] information out on the next message you
[29:50] were gonna send anyway in fact I I don't
### chunk 39 [29:50]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

ion out on the next message you
[29:50] were gonna send anyway in fact I I don't[29:53] think the time at which the replicas
[29:58] execute the request is critical because
[30:02] nobody's waiting for it at least if
[30:04] there's no failures if there's no
[30:06] failures replicas executing the request
[30:10] isn't really on the critical path like
[30:12] the client isn't waiting for them the
[30:13] client saw me waiting for the leader to
[30:15] execute so it may not be that it may not
[30:20] affect client perceived latency sort of
[30:23] exactly how this gets staged
[30:37] all right one question you should ask is
[30:45] why does the system why is the system so
[30:48] focused on blogs what are the logs doing
[30:52] and it's sort of worth trying to come up
[30:54] with an explicit answers to that one
[30:56] answer to why the system is totally
### chunk 40 [30:56]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

with an explicit answers to that one
[30:56] answer to why the system is totally[31:00] focused on logs is that the log is the
[31:04] kind of mechanism by which the leader
[31:05] orders operations it's vital for these
[31:08] replicated state machines that all the
[31:10] replicas apply not just the same client
[31:13] operations to their start but the same
[31:15] operations in the same order but they
[31:18] all have to apply that these operations
[31:20] coming from the clients in the same
[31:22] order and the log among many other
[31:24] things is part of the machinery by which
[31:26] the or the leader assigns an order to
[31:30] the incoming client operations I give
[31:32] you know ten clients send operations to
[31:34] the leader at the same time the client
[31:36] the leader has to pick pick an order
[31:37] make sure everybody all the replicas
### chunk 41 [31:37]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

he leader has to pick pick an order
[31:37] make sure everybody all the replicas[31:39] obey that order and the log is you know
[31:41] the fact that the log has numbered slots
[31:44] as part of half a meter expresses the
[31:46] order it's chosen another use of the log
[31:52] is that between this point and this
[31:56] point server 3 has received an operation
[32:00] that it is not yet sure is committed and
[32:02] it cannot execute it yet it has to put
[32:04] the this operation aside somewhere until
[32:07] the increment to the leader commit value
[32:11] comes in and so another thing that the
[32:13] log is doing is that on the followers
[32:15] the log is the place where the follower
[32:17] sort of sets aside operations that are
[32:18] still tentative that have arrived but
[32:20] are not yet known to be committed and
### chunk 42 [32:20]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

ll tentative that have arrived but
[32:20] are not yet known to be committed and[32:21] they may have to be thrown away as we'll
[32:23] see so that's another use I'm the I sort
[32:27] of do love that use on the leader side
[32:29] is that the leader needs to remember
[32:33] operations in its log because it may
[32:36] need to retransmit them to followers if
[32:38] some followers offline maybe it's
[32:40] something briefly happened to its
[32:41] network
[32:42] action or something misses some messages
[32:44] the leader needs to be able to resend
[32:46] log messages that any followers missed
[32:49] and so the leader needs a place where
[32:50] can set aside copies of messages of
[32:52] client requests even ones that it's
[32:54] already executed in order to be able to
[32:56] resend them to the client I mean we send
### chunk 43 [32:56]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

executed in order to be able to
[32:56] resend them to the client I mean we send[33:00] them to replicas that missed missed that
[33:04] operation and a final reason for all of
[33:05] them to keep the log is that at least in
[33:07] the world of figure 2 if a server
[33:11] crashes and restarts and wants to rejoin
[33:15] and you really need if it you really
[33:17] want a server that crashes - in fact we
[33:19] start and rejoin the raft cluster
[33:21] otherwise you're now operating with only
[33:23] two out of three servers and you can't
[33:24] survive any more failures we need to
[33:26] reincorporate failed and rebooted
[33:29] servers and the log is sort of where or
[33:31] what a server rebooted server uses the
[33:34] log persisted to its disk because one of
[33:37] the rules is that each raft server needs
[33:39] to write its log to its disk where it
### chunk 44 [33:39]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

les is that each raft server needs
[33:39] to write its log to its disk where it[33:41] will still be after it crashes and
[33:42] restarts that log is what the server
[33:44] uses or replays the operations in that
[33:48] log from the beginning to sort of create
[33:50] its state as of when it crashed and then
[33:52] then it carries on from there so the log
[33:54] is also used as part of the persistence
[33:56] plan as a sequence of commands to
[33:58] rebuild the state
[34:16] well ultimately okay so the question is
[34:20] suppose the leader is capable of
[34:23] executing a thousand client commands a
[34:25] second and the followers are only
[34:26] incapable of executing a hundred client
[34:28] commands per second that's sort of
[34:30] sustained rate you know full speed v so
[34:36] one thing to note is that the the
[34:41] replicas the followers acknowledge
### chunk 45 [34:41]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

36] one thing to note is that the the
[34:41] replicas the followers acknowledge[34:43] commands before they execute them so
[34:45] they mate rate at which they acknowledge
[34:47] and accumulate stuff in their logs is
[34:48] not limited so you know maybe they can
[34:51] acknowledge that a thousand requests per
[34:52] second if they do that forever then they
[34:55] will build up unbounded size logs
[34:57] because their execution rate falls it
[35:00] will fall on an unbounded amount behind
[35:02] the rate at which the leader has given
[35:04] the messages sort of under the rules of
[35:06] our game and so what that means they
[35:08] will eventually run out of memory at
[35:11] some point so after they have a billion
[35:13] after they fall a billion log entries
[35:15] behind those just like they'll call the
[35:16] memory allocator for space for a new
### chunk 46 [35:16]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

nd those just like they'll call the
[35:16] memory allocator for space for a new[35:18] blog entry and it will fail so yeah and
[35:22] Raph doesn't Raph doesn't have the flow
[35:27] controls that's required to cope with
[35:30] this so I think in a real system you
[35:34] would actually need you know probably
[35:36] piggybacked and doesn't need to be
[35:37] real-time but you probably need some
[35:39] kind of additional communication here
[35:43] that says well here's how far I've
[35:45] gotten in execution so that the leader
[35:48] can say well you know too many thousands
[35:50] of requests ahead of the point in which
[35:53] the followers have executed yes I think
[35:55] there's probably you know in a
[35:56] production system that you're trying to
[35:58] push to the absolute max you would you
[36:01] might well need an extra message to
### chunk 47 [36:01]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

sh to the absolute max you would you
[36:01] might well need an extra message to[36:03] throttle the leader if it got too far
[36:05] ahead
[36:31] okay so the question is if if one of
[36:36] these servers crashes it has this log
[36:38] that it persisted to disk because that's
[36:39] one of the rules of figure two so the
[36:42] server will be able to be just logged
[36:43] back from disk but of course that server
[36:47] doesn't know how far it got in executing
[36:49] the log and also it doesn't know at
[36:52] least when it first reboots by the rule
[36:54] that figure two it doesn't even know how
[36:56] much of the log is committed so the
[36:59] first answer to your question is that
[37:00] immediately after a restart you know
[37:03] after a server crashes and restarts and
[37:05] reads its log it is not allowed to do
### chunk 48 [37:05]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

 a server crashes and restarts and
[37:05] reads its log it is not allowed to do[37:07] anything with the log because it does
[37:10] not know how far the system has
[37:11] committed in its log maybe as long as
[37:14] has a thousand uncommitted entries and
[37:16] zero committed entries for all it notes
[37:18] so
[37:24] it's a leader dye support that doesn't
[37:26] help either but let's suppose they've
[37:28] all crashed this is getting ahead of its
[37:32] getting a bit ahead of me but well
[37:33] suppose they've all crashed and so all
[37:34] they have is the state that was marked
[37:37] as non-volatile in figure 2 which
[37:40] includes the log and maybe the latest
[37:42] term and so they don't know some if
[37:45] there's a crash but they all crash and
[37:46] they always start none of them knows
[37:48] initially how far they had been have
### chunk 49 [37:48]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

hey always start none of them knows
[37:48] initially how far they had been have[37:52] executed before the crash so what
[37:55] happens is that you leader election one
[37:57] of them gets picked as a leader and that
[38:00] leader if you sort of track through what
[38:03] figure 2 says about how a pendant Rees
[38:06] is supposed to work the leader will
[38:08] actually figure out as a byproduct of
[38:10] sending out a pendant or sending out the
[38:12] first heartbeat really it'll fake it'll
[38:16] figure out what the latest point is
[38:19] basically that that all of the that a
[38:28] majority of the replicas agree on their
[38:30] laws because that's the commit point
[38:33] another way of looking at it is that
[38:35] once you choose a leader through the
[38:37] append entries mechanism the leader
[38:39] forces all of the other replicas to have
### chunk 50 [38:39]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

nd entries mechanism the leader
[38:39] forces all of the other replicas to have[38:41] identical logs to the leader and at that
[38:44] point plus a little bit of extra the
[38:46] paper explains at that point since the
[38:48] leader knows that it's forced all the
[38:50] replicas to have it I didn't have logs
[38:52] that are identicals to it then it knows
[38:54] that all the replicas must also have a
[38:57] there must be a majority of replicas
[39:00] with that all those log injuries in that
[39:03] logs which are now are identical must
[39:04] also be committed because they're held
[39:06] on a majority of replicas and at that
[39:09] point a leader you know the append
[39:13] entries code described in Figure 2 for
[39:15] the leader will increment the leaders
[39:17] commit point and everybody can now
[39:19] execute the entire log from the
### chunk 51 [39:19]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

9:17] commit point and everybody can now
[39:19] execute the entire log from the[39:21] beginning and recreate their state from
[39:24] scratch possibly extremely laborious Lee
[39:29] so that's what figure two says it's
[39:32] obviously this be executing from scratch
[39:34] is not very attractive but it's where
[39:37] the basic protocol does and we'll see
[39:40] tomorrow that the the sort of version of
[39:42] this is more efficient to use as
[39:44] checkpoints and we'll talk about
[39:45] tomorrow okay so this was a sequence in
[39:50] sort of ordinary non failure operation
[39:55] another thing I want to briefly mention
[39:57] is what this interface looks like you've
[40:00] probably all seen a little bit of it due
[40:03] to working on the labs but roughly
[40:05] speaking if you have let's say that this
[40:07] key value layer with its state and the
### chunk 52 [40:07]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

g if you have let's say that this
[40:07] key value layer with its state and the[40:12] raft layer underneath it there's on each
[40:16] replica there's really two main pieces
[40:18] of the interface between them there's
[40:20] this method by which the key value layer
[40:24] can relay if a client sends in a request
[40:26] the key value layer has to give it to
[40:27] wrap and say please you know fit this
[40:29] request into the log somewhere and
[40:31] that's the start function that you'll
[40:36] see in Raph go and really just takes one
[40:40] argument the client command the key
[40:44] value they're saying please I got this
[40:45] command to get into the log and tell me
[40:47] when it's committed and the other piece
[40:50] of the interface is that by and by the
[40:54] raft layer will notify the key value
[40:55] layer that AHA that operation that you
### chunk 53 [40:55]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

t layer will notify the key value
[40:55] layer that AHA that operation that you[40:58] sent to me in a start command a while
[40:59] ago which may well not be the most
[41:01] recent start right there you know a
[41:03] hundred client commands could come in
[41:05] and cause calls to start before any of
[41:07] them are committed so by and by this
[41:11] upward communication is takes the form
[41:14] of a message on a go channel that the
[41:16] raft library sends on and key value
[41:20] layer is supposed to read from so
[41:23] there's this apply called the apply
[41:28] channel and on it on it you send apply
[41:31] message
[41:37] this start and of course you need the
[41:39] the key value layer needs to be able to
[41:42] match up message that receives an apply
[41:44] channel with calls to start that it made
[41:47] and so the start command actually
### chunk 54 [41:47]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

annel with calls to start that it made
[41:47] and so the start command actually[41:49] returns enough information for that
[41:52] matchup to happen it returns the index
[41:54] that start functions basically returns
[41:58] the index in the log where if this
[42:00] command is committed which it might not
[42:02] be it'll be committed at this index and
[42:05] I think it also returns the current term
[42:07] and some other stuff we don't care about
[42:08] very much and then this apply message is
[42:11] going to contain the index command and
[42:26] all the replicas will get these apply
[42:27] messages so they'll all know though I
[42:29] should apply this command figure out
[42:33] what this command means and apply it to
[42:35] my local State and they also get the
[42:37] index the index is really only useful
[42:38] I'm the leader so it can figure out what
### chunk 55 [42:38]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

the index is really only useful
[42:38] I'm the leader so it can figure out what[42:42] client would what client requests were
[42:43] talking about
[43:00] by
[43:14] the answer a slightly different question
[43:16] let's suppose the client sends any
[43:18] request in let's say it's a put or a get
[43:21] could be put or again it doesn't really
[43:23] matter I'd say it to get the point in
[43:29] which the it's a client sense and again
[43:32] and waits for a response the point at
[43:33] which the leader will send a response at
[43:37] all is after the leader knows that
[43:39] command is committed so this is going to
[43:41] be a sort of get reply so the client
[43:48] doesn't see anything back I mean and so
[43:52] that means in terms of the actual
[43:54] software stack that means that the key
[43:56] value the RPC will arrive the key value
### chunk 56 [43:56]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

re stack that means that the key
[43:56] value the RPC will arrive the key value[43:59] layer will call the start function the
[44:02] start function will return to the key
[44:03] value layer but the key value layer will
[44:06] not yet reply to the client because it
[44:08] does not know if it's good actually it
[44:10] hasn't executed the clients request now
[44:12] it doesn't even know if it ever will
[44:13] because it's not sure if the request is
[44:16] going to be committed right in the
[44:18] situation which may not be committed is
[44:20] if the key value layer you know guess
[44:23] the request calls start and immediately
[44:25] after starboard turn two crashes right
[44:27] certainly hasn't sent out its apply what
[44:28] append messages or whatever
[44:30] nothing's be committed yep so so the
[44:33] game is start returns time passes the
### chunk 57 [44:33]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

thing's be committed yep so so the
[44:33] game is start returns time passes the[44:36] relevant apply message corresponding to
[44:40] that client request appears to the key
[44:42] value server on the apply channel and
[44:44] only then and that causes the key value
[44:47] server to execute the request and send
[44:50] her a plot
[44:58] and that's like all this is very
[45:00] important when it doesn't really matter
[45:02] if all everything goes well but if
[45:04] there's a failure we're now at the point
[45:06] where we start worrying about theatres I
[45:07] mean extremely interested in if there
[45:09] was a failure what did the client see
[45:13] all right and so one thing that does
[45:18] come up is that all of you should be
[45:23] familiar with this that at least
[45:24] initially one interesting thing about
[45:26] the logs is that they may not be
### chunk 58 [45:26]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

] initially one interesting thing about
[45:26] the logs is that they may not be[45:28] identical there are a whole bunch of
[45:30] situations in which at least for brief
[45:33] periods of time the ends of the
[45:36] different replicas logs may diverge like
[45:39] for example if a leader starts to send
[45:41] out a round of append messages but
[45:43] crashes before it's able to send all
[45:45] them out you know that'll mean that some
[45:46] of the replicas that got the append
[45:48] message will append you know that new
[45:50] log entry and the ones that didn't get
[45:51] that append messages RPC won't have
[45:54] appended them so it's easy to see that
[45:56] the logs are I'm gonna diverge sometimes
[45:58] the good news is that the the way a raft
[46:02] works actually ends up forcing the logs
[46:05] to be identical after a while there may
### chunk 59 [46:05]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

ctually ends up forcing the logs
[46:05] to be identical after a while there may[46:08] be transient differences but in the long
[46:10] run all the logs will sort of be
[46:13] modified by the leader until the leader
[46:15] insurers are all identical and only then
[46:17] are they executed okay so I think the
[46:24] next there's really two big topics to
[46:27] talk about here for raft one is how
[46:29] leader election works which is lab two
[46:31] and the other is how the leader deals
[46:35] with the different replicas logs
[46:37] particularly after failure so first I
[46:39] want to talk about leader election
[46:44] question to ask is how come the system
[46:47] even has a leader why do we need a
[46:48] leader the part of the answer is you do
[46:51] not need a leader to build a system like
[46:53] this you it is possible to build an
### chunk 60 [46:53]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

need a leader to build a system like
[46:53] this you it is possible to build an[46:56] agreement system by which a cluster of
[46:59] servers agrees you know the sequence of
[47:02] entries in a log without having any kind
[47:04] of designated leader
[47:05] and indeed the original pack so system
[47:07] which the paper refers to original Paxos
[47:09] did not have a leader so it's possible
[47:13] the reason why raft has a leader is
[47:15] basically that there's probably a lot of
[47:18] reasons but one of the foremost reasons
[47:20] is that you can build a more efficient
[47:22] in the common case in which the server's
[47:24] don't fail it's possible to build a more
[47:27] efficient system if you have a leader
[47:28] because with a designated leader
[47:30] everybody knows who the leader is you
[47:33] can basically get agreement on requests
### chunk 61 [47:33]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

body knows who the leader is you
[47:33] can basically get agreement on requests[47:37] that with one round of messages per
[47:39] request where as leader of this systems
[47:41] have more of the flavor of well you need
[47:43] a first round to kind of agree on a
[47:45] temporary leader and then a second round
[47:47] actually send out the requests so it's
[47:50] probably the case that use of a leader
[47:53] now speeds up the system by a factor two
[47:56] and it also makes it sort of easier to
[47:58] think about what's going on raft goes
[48:04] through a sequence of leaders and it
[48:08] uses these term numbers in order to sort
[48:11] of disambiguate which leader we're
[48:13] talking about it turns out that
[48:14] followers don't really need to know the
[48:15] identity of the leader they really just
[48:17] need to know what the current term
### chunk 62 [48:17]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

entity of the leader they really just
[48:17] need to know what the current term[48:18] number is each term has at most one
[48:23] leader that's a critical property you
[48:25] know for every term there might be no
[48:27] leader during that term or there might
[48:29] be one leader but there cannot be two
[48:31] leaders during the same term every term
[48:34] has it must most one leader how do the
[48:42] leaders get created in the first place
[48:44] every raft server keeps this election
[48:48] timer which is just a it's basically
[48:50] just out of time that it has recorded
[48:52] that says well if that time occurs I'm
[48:54] going to do something and the something
[48:56] that it does is that if an entire leader
[48:59] election period expires without the
[49:02] server having heard any message from the
[49:04] current leader then the server sort of
### chunk 63 [49:04]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

having heard any message from the
[49:04] current leader then the server sort of[49:08] assumes probably that the current leader
[49:10] is dead and starts an election so we
[49:12] have this election timer
[49:17] and if it expires we start an election
[49:28] and what it means to start an election
[49:30] is basically that you increment the term
[49:35] the the candidate the server that's
[49:38] decided it's going to be a candidate and
[49:39] sort of force a new election first
[49:41] increments this term because it wants
[49:43] them to be a new leader namely itself
[49:45] and you know leader a term can't have
[49:47] more than one leader so we got to start
[49:49] a new term in order to have a new leader
[49:51] and then it sends out these requests
[49:54] boats are pea seeds I'm going to send
[50:00] out a full round of request votes and
### chunk 64 [50:00]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

ts are pea seeds I'm going to send
[50:00] out a full round of request votes and[50:02] you may only have to send out n minus
[50:05] one requests votes because one of the
[50:06] rules is that a new candidate always
[50:08] votes for itself in the election so one
[50:13] thing to note about this is that it's
[50:16] not quite the case that if the leader
[50:17] didn't fail we won't have an election
[50:19] but if the leader does fail then we will
[50:22] have election an election assuming any
[50:24] other server is up because some day the
[50:26] other servers election timers go will go
[50:28] off but as leader didn't fail we might
[50:30] still unfortunately get an election so
[50:32] if the network is slow or drops a few
[50:34] heartbeats or something we may end up
[50:37] having election timers go off and even
[50:38] though there was a perfectly good leader
### chunk 65 [50:38]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

election timers go off and even
[50:38] though there was a perfectly good leader[50:40] we may nevertheless have a new election
[50:42] so we have to sort of keep that in mind
[50:43] when we're thinking about the
[50:44] correctness and what that in turn means
[50:48] is that if there's a new election it
[50:50] could easily be the case that the old
[50:52] leader is still hanging around and still
[50:54] thinks it's the leader like if there's a
[50:56] network partition for example and the
[50:58] old leader is still alive and well in a
[51:00] minority partition the majority
[51:03] partition may run an election and indeed
[51:05] a successful election and choose a new
[51:06] leader all totally unknown to the
[51:09] previous leader so we also have to worry
[51:11] about you know what's that previous
[51:13] leader gonna do since it does not know
### chunk 66 [51:13]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

out you know what's that previous
[51:13] leader gonna do since it does not know[51:15] there was a new election yes
[51:42] okay so the question is are there can
[51:44] there be pathological cases in which for
[51:46] example one-way network communication
[51:50] can prevent the system from making
[51:52] progress I believe the answer is yes
[51:54] certainly so for example if the current
[51:56] leader if its network somehow half fails
[52:00] in a way the current leader can send out
[52:02] heartbeats
[52:04] but can't receive any client requests
[52:07] then the heartbeats that it sends out
[52:09] which are delivered because it's
[52:11] outgoing network connection works its
[52:13] outgoing heartbeats will suppress any
[52:18] other server from starting an election
[52:20] but the fact that it's incoming Network
[52:22] why or apparently is broken will prevent
### chunk 67 [52:22]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

fact that it's incoming Network
[52:22] why or apparently is broken will prevent[52:24] it from hearing and executing any client
[52:26] commands it's absolutely the case that
[52:29] raft is not proof against all sort of
[52:35] all crazy Network problems that can come
[52:37] up I believe the ones I've thought about
[52:38] I believe are fixable in the sense that
[52:42] the we could solve this one by having a
[52:46] sort of requiring a two-way heartbeat in
[52:49] which if the leader sends out heartbeats
[52:51] but you know there were in which
[52:53] followers are required to reply in some
[52:55] way to heartbeats I guess they are
[52:56] already required to apply if the leader
[52:59] stop seeing replies to its heartbeats
[53:01] then after some amount of time and which
[53:04] is seasonals replies the leader decides
### chunk 68 [53:04]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

er some amount of time and which
[53:04] is seasonals replies the leader decides[53:06] to step down I feel like that specific
[53:09] issue can be fixed and many others can
[53:12] too but I but you know you're absolutely
[53:16] right that very strange things can
[53:17] happen to networks including some that
[53:19] the protocol is not prepared for
[53:28] okay so we got these meter elections we
[53:32] need to ensure that there is at most at
[53:33] most one meter per term
[53:35] how does Rath do that well Rath requires
[53:38] in order to be elected for a term Raft
[53:40] requires a candidate to get yes votes
[53:42] from a majority of the server's the
[53:46] servers and each server will only cast
[53:47] one yes vote per term so in any given
[53:52] term you know it basically means that in
[53:55] any given term Easter votes only once
### chunk 69 [53:55]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

ou know it basically means that in
[53:55] any given term Easter votes only once[53:58] for only one candidate you can't have
[54:01] two candidates both get a majority of
[54:03] votes because everybody votes only once
[54:06] so the majorities majority rule causes
[54:09] there to be at most one winning
[54:11] candidate and so then we get at most one
[54:17] candidate elected per turn
[54:24] and in addition critically the majority
[54:28] rule means that you can get elected even
[54:31] if some servers have crashed right if a
[54:34] minority of servers are crashed aren't
[54:36] available and network problems we can
[54:37] still elect a leader if more than half a
[54:39] crash or not available or in another
[54:41] partition or something then actually the
[54:43] system will just sit there trying again
[54:44] and again to elect a leader and never
### chunk 70 [54:44]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

m will just sit there trying again
[54:44] and again to elect a leader and never[54:47] elect one if it cannot in fact they're
[54:49] not a majority of live servers if an
[54:54] election succeeds everybody would be
[54:57] great if everybody learned about it I
[54:58] mean need to ask ourselves how do all
[55:01] the parties learn learn what happened
[55:02] the server that wins an election
[55:04] assuming it doesn't crash the server
[55:07] that wins election will actually see a
[55:09] majority or positive votes for its
[55:12] request vote from a majority of the
[55:15] other servers so the candidates running
[55:17] the election that wins it the Kennedy
[55:19] that wins the election will actually
[55:20] know directly uh I got a majority of
[55:22] votes but nobody else directly knows who
[55:26] the winner was or whether anybody one so
### chunk 71 [55:26]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

 nobody else directly knows who
[55:26] the winner was or whether anybody one so[55:28] the way that the candidate informs other
[55:30] servers is that heartbeat the rules and
[55:33] figure to say oh if you're in an
[55:34] election your immediately required to
[55:36] send out an independent
[55:37] trees to all the other servers now the
[55:39] append entries that heartbeat append
[55:41] entries doesn't explicitly say I won the
[55:45] election you know I'm a leader for term
[55:47] 23 it's a little more subtle than that
[55:51] the the way the information is
[55:53] communicated is that no one is allowed
[55:57] to send out an append entries unless
[56:00] they're a leader for that term so the
[56:02] fact that I I'm a you know I'm a server
[56:05] and I saw oh there's an election for
[56:07] term 19 and then by-and-by I sent an
### chunk 72 [56:07]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

nd I saw oh there's an election for
[56:07] term 19 and then by-and-by I sent an[56:09] append entries whose term is 19 that
[56:12] tells me that somebody I don't know who
[56:15] but somebody won the election so that's
[56:18] how the other servers knows they were
[56:19] receiving append entries for that term
[56:21] and that append entries also has the
[56:24] effect of resetting everybody's election
[56:27] time timer so as long as the leader is
[56:30] up and it sends out heartbeat messages
[56:32] or append entries at least you know at
[56:34] the rate that's supposed to every time a
[56:36] server receives an append entries it'll
[56:38] reset its selection timer and sort of
[56:42] suppress anybody from being a new
[56:45] candidate so as long as everything's
[56:47] functioning the repeated heartbeats will
[56:49] prevent any further elections of course
### chunk 73 [56:49]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

ing the repeated heartbeats will
[56:49] prevent any further elections of course[56:52] it the network fails or packets are
[56:53] dropped there may nevertheless be an
[56:55] election but if all goes well we're sort
[56:57] of unlikely to get an election this
[57:03] scheme could fail in the sense that it
[57:05] can't fail in the sense of electing to
[57:07] leaders fair term but it can fail in the
[57:09] sense of electing zero leaders for a
[57:11] term that's sort of morningway it may
[57:14] fail is that if too many servers are
[57:16] dead or unavailable or a bad network
[57:18] connection so if you can't assemble a
[57:19] majority you can't be elected nothing
[57:21] happens the more interesting way in
[57:24] which an election can fail is if
[57:27] everybody's up you know there's no
[57:30] failures no packets are dropped but two
### chunk 74 [57:30]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

erybody's up you know there's no
[57:30] failures no packets are dropped but two[57:33] leaders become candidate close together
[57:35] enough in time that they split the vote
[57:38] between them or say three leaders
[57:45] so supposing we have three liters
[57:46] supposing we have a three replica system
[57:49] all their election timers go off at the
[57:51] same time every server both for itself
[57:54] and then when each of them receives a
[57:57] request vote from another server well
[57:59] it's already cast its vote for itself
[58:00] and so it says no so that means that it
[58:02] all three of the server's needs to get
[58:04] one vote each nobody gets a majority and
[58:05] nobody's elected so then their election
[58:09] timers will go off again because the
[58:11] election timers only be said if it gets
[58:12] an append entries but there's no leader
### chunk 75 [58:12]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

n timers only be said if it gets
[58:12] an append entries but there's no leader[58:14] so no append entries they'll all have
[58:16] their election timers go off again and
[58:17] if we're unlucky
[58:19] they'll all go off at the same time
[58:20] they'll all go for themselves nobody
[58:22] will get a majority so so clearly I'm
[58:27] sure you're all aware at this point
[58:28] there's more to this story and the way
[58:31] Raft makes this possibility of split
[58:35] votes unlikely but not impossible
[58:38] is by randomizing these election timers
[58:41] so the way to think of it and the
[58:44] randomization the way to think of it is
[58:46] that supposing you have some time line
[58:47] I'm gonna draw a vents on there's some
[58:52] point at which everybody received the
[58:54] last append entries right and then maybe
### chunk 76 [58:54]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

at which everybody received the
[58:54] last append entries right and then maybe[58:57] the server died let's just assume the
[58:58] server send out a last heartbeat and
[59:01] then died well all of the followers have
[59:08] this we set their election timers when
[59:11] they received at the same time because
[59:13] they probably all receive this append
[59:14] enters at the same time they all reset
[59:16] their election timers for some point in
[59:18] the future the future but they chose
[59:21] different random times in the future
[59:23] which then we're gonna go off
[59:25] so it's suppose the dead leader server
[59:27] one so now server two and server 3 at
[59:30] this point set their election timers for
[59:32] a random point in the future let's say
[59:34] server to set their I like some timer to
[59:37] go off here and server 3 set its
### chunk 77 [59:37]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

erver to set their I like some timer to
[59:37] go off here and server 3 set its[59:41] election timer to go off there and the
[59:43] crucial point about this picture is that
[59:46] assuming they picked different random
[59:48] numbers one of them is first and the
[59:51] other one is second right that's what's
[59:54] going on here and the one that's first
[59:56] assuming
[59:58] this gap is big enough the one that's
[01:00:00] first it's election time will go off
[01:00:01] first before the other ones election
[01:00:02] timer and if we're close were not
[01:00:05] unlucky
[01:00:06] it'll have time to send out a full round
[01:00:08] of vote requests and get answers from
[01:00:11] everybody who everybody's alive before
[01:00:13] the second election timer goes off from
[01:00:16] any other server so does everybody see
### chunk 78 [01:00:16]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

d election timer goes off from
[01:00:16] any other server so does everybody see[01:00:22] how the randomization D synchronizes
[01:00:26] these candidates unfortunately there's a
[01:00:30] bit of art in setting the contents
[01:00:33] constants for these election timers
[01:00:34] there's some sort of competing
[01:00:36] requirements you might want to fulfill
[01:00:40] so one obvious requirement is that the
[01:00:43] election timer has to be at least as
[01:00:45] long as the expected interval between
[01:00:47] heartbeats
[01:00:47] you know this is pretty obvious that the
[01:00:49] leader sends out heartbeats every
[01:00:51] hundred milliseconds you better make
[01:00:53] sure there's no point in having the
[01:00:55] election time or anybody's election time
[01:00:57] or ever go off Borja for 100
[01:00:58] milliseconds because then it will go off
### chunk 79 [01:00:58]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

or ever go off Borja for 100
[01:00:58] milliseconds because then it will go off[01:01:00] before the lower limit is certainly the
[01:01:06] lower limit is one heartbeat interval in
[01:01:08] fact because the network may drop
[01:01:10] packets you probably want to have the
[01:01:13] minimum election timer value be a couple
[01:01:16] of times the heartbeat interval so 400
[01:01:18] millisecond heartbeats you probably want
[01:01:20] to have the very shortest possible
[01:01:21] election time or be you know say 300
[01:01:24] milliseconds you know three times the
[01:01:26] heartbeat interval so that's the sort of
[01:01:29] minimum is the heart heartbeat so this
[01:01:33] frequent you want the minimum to be you
[01:01:35] know a couple of times that or here so
[01:01:39] what about the maximum you know you're
[01:01:40] gonna presumably randomize uniformly
### chunk 80 [01:01:40]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

bout the maximum you know you're
[01:01:40] gonna presumably randomize uniformly[01:01:43] over some range of times you know where
[01:01:45] should we set the kind of maximum time
[01:01:50] that we're randomizing over there's a
[01:01:54] couple of considerations here in a real
[01:01:57] system you know this maximum time effect
[01:02:04] how quickly the system can recover from
[01:02:06] failure because remember from the time
[01:02:09] at which the server fails until the
[01:02:11] first election timer goes off the whole
[01:02:14] system is frozen there's no leader you
[01:02:17] know the clients requests are being
[01:02:18] thrown away because there's no leader
[01:02:20] and we're not assigning a new leader
[01:02:22] even though you know presumably these
[01:02:24] other servers are up so the beer we
[01:02:27] choose this maximum the long or delay
### chunk 81 [01:02:27]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

r servers are up so the beer we
[01:02:27] choose this maximum the long or delay[01:02:29] we're imposing on clients before
[01:02:32] recovery occurs you know whether that's
[01:02:34] important depends on sort of how high
[01:02:38] performance we need this to be and how
[01:02:40] often we think there will be failures
[01:02:42] failures happen once a year then who
[01:02:44] cares
[01:02:46] we're expecting failures frequently we
[01:02:48] may care very much how long it takes to
[01:02:51] recover okay so that's one consideration
[01:02:53] the other consideration is that this gap
[01:02:56] that is the expected gap in time between
[01:02:59] the first time are going off and the
[01:03:01] second timer going off this gap really
[01:03:04] in order to be useful has to be longer
[01:03:07] than the time it takes for the candidate
### chunk 82 [01:03:07]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

o be useful has to be longer
[01:03:07] than the time it takes for the candidate[01:03:09] to assemble votes from everybody that is
[01:03:12] longer than the expected round-trip time
[01:03:15] the amount of time it takes to send an
[01:03:16] RPC and get the response and so maybe it
[01:03:19] takes 10 milliseconds to send an RPC and
[01:03:21] get a response a response from all the
[01:03:25] other servers and if that's the case we
[01:03:27] need to make maximum at least long
[01:03:28] enough that there's pretty likely to be
[01:03:30] 10 milliseconds difference between the
[01:03:32] smallest random number and the next
[01:03:34] smallest random number
[01:03:40] and for you the test code will get upset
[01:03:46] if you if you don't recover from a
[01:03:54] leader failure in a couple seconds and
[01:03:56] so just pragmatically you need to tune
### chunk 83 [01:03:56]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

ailure in a couple seconds and
[01:03:56] so just pragmatically you need to tune[01:03:58] this maximum down so that it's highly
[01:04:00] likely that you'll be able to complete a
[01:04:03] leader election within a few seconds but
[01:04:05] that's not a very tight constraint any
[01:04:09] questions about the election time outs
[01:04:13] one tiny point is that you want to
[01:04:19] choose new random time outs every time
[01:04:23] there's every time you every time I node
[01:04:26] sets it to like me sets its election
[01:04:28] timer that is don't choose a random
[01:04:31] number when the server is first created
[01:04:34] and then we use that same number over
[01:04:36] and over again because you make an
[01:04:37] unlucky choice that is you choose this
[01:04:39] one server happens by ill chance to
[01:04:42] choose the same random number as another
### chunk 84 [01:04:42]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

ver happens by ill chance to
[01:04:42] choose the same random number as another[01:04:44] server that means that you're gonna have
[01:04:46] split votes over and over again forever
[01:04:48] that's why you want to almost certainly
[01:04:51] choose a different a new fresh random
[01:04:53] number for the election time out value
[01:04:56] every time you reset the timer all right
[01:05:02] so the final issue about leader election
[01:05:06] suppose we are in this situation where
[01:05:09] the old leaders partition you know the
[01:05:11] network cable is broken and the old
[01:05:12] leader is sort of out there with a
[01:05:14] couple clients and a minority of servers
[01:05:17] and there's a majority in the other half
[01:05:20] of the network and the majority of the
[01:05:21] new half of the network elects a new
### chunk 85 [01:05:21]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

 network and the majority of the
[01:05:21] new half of the network elects a new[01:05:22] leader what about the old leader why why
[01:05:28] won't the old leader cause incorrect
[01:05:32] execution
[01:06:06] yes to two potential problems one is or
[01:06:09] one some non problem is that if there's
[01:06:12] a leader off in another partition and it
[01:06:14] doesn't have a majority then the next
[01:06:17] time a client sends it a request that
[01:06:20] that leader that you know in a partition
[01:06:24] with a minority yeah it'll send out
[01:06:25] append entries but because it's in the
[01:06:27] minority partition it won't be able to
[01:06:29] get responses back from a majority of
[01:06:31] the server's including itself and so it
[01:06:33] will never commit the operation it will
[01:06:36] never execute it
### chunk 86 [01:06:33]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

t
[01:06:33] will never commit the operation it will
[01:06:36] never execute it[01:06:37] it'll never respond to the client saying
[01:06:39] that it executed it either and so that
[01:06:42] means that yeah an old server often a
[01:06:45] different partition people many clients
[01:06:47] may send a request but they'll never get
[01:06:49] responses so no client will be fooled
[01:06:54] into thinking that that old server
[01:06:56] executed anything for it the other sort
[01:07:02] of more tricky issue which actually I'll
[01:07:05] talk about in a few minutes is the
[01:07:07] possibility that before server fails it
[01:07:10] sends out append entries to a subset of
[01:07:14] the servers and then crashes before
[01:07:17] making a commission and as a very
[01:07:21] interesting question which I'll probably
[01:07:24] spend a good 45 minutes talking about
### chunk 87 [01:07:24]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

ng question which I'll probably
[01:07:24] spend a good 45 minutes talking about[01:07:27] and so actually before I turn to the
[01:07:30] back topic in general any more questions
[01:07:33] about in leader election okay
[01:07:42] okay so how about the contents of the
[01:07:44] logs and how in particular how a newly
[01:07:49] elected leader possibly picking up the
[01:07:51] pieces after an awkward crash of the
[01:07:54] previous leader how does a newly elected
[01:07:56] leader sort out the possibly divergent
[01:07:59] logs on the different replicas in order
[01:08:02] to restore sort of consistent state in
[01:08:06] the system all right so the first
[01:08:14] question is what can think this is this
[01:08:17] whole topic it's really only interesting
[01:08:19] after a server crashes right if the
[01:08:21] server stays up then relatively few
### chunk 88 [01:08:21]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

ter a server crashes right if the
[01:08:21] server stays up then relatively few[01:08:25] things can go wrong if we have a server
[01:08:26] that's up and has a majority you know
[01:08:28] during the period of time when it's up
[01:08:29] and has a majority it just tells the
[01:08:34] followers what the logs should look like
[01:08:35] and the followers are not allowed to
[01:08:37] disagree they're required to accept they
[01:08:39] just do by the rules of figure two if
[01:08:41] they've been more or less keeping up you
[01:08:43] know they just take whatever the leader
[01:08:44] sends them independent reason appended
[01:08:46] to the log and obey commit messages and
[01:08:48] execute there's hardly anything to go
[01:08:50] wrong the things that go wrong in Rapp
[01:08:52] go wrong when a the old leader crashes
### chunk 89 [01:08:52]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

e things that go wrong in Rapp
[01:08:52] go wrong when a the old leader crashes[01:08:55] sort of midway through you know sending
[01:08:58] out messages or a new leader crashes you
[01:09:01] know sort of just after it's been
[01:09:03] elected but before it's done anything
[01:09:06] very useful so one thing we're very
[01:09:10] interested in is what can the logs look
[01:09:11] like after some sequence of crashes okay
[01:09:16] so here's an example supposing we have
[01:09:19] two servers and the way I'm gonna draw
[01:09:26] out these diagrams because we're gonna
[01:09:27] be looking a lot at a lot of sort of
[01:09:30] situations where the logs look like this
[01:09:32] and we're gonna be wondering is that
[01:09:34] possible and what happens if they do
[01:09:36] look like that so my notation is going
[01:09:38] to be I'm gonna write out log entries
### chunk 90 [01:09:38]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

ke that so my notation is going
[01:09:38] to be I'm gonna write out log entries[01:09:40] for each of the servers sort of aligned
[01:09:44] to indicate slots corresponding slots in
[01:09:47] the log and the values I'm going to
[01:09:50] write here are the term numbers rather
[01:09:53] than
[01:09:54] client operations I'm going to you know
[01:09:56] this is slot one this is thought to
[01:09:59] everybody saw a command from term three
[01:10:02] in slot 1 and server tuned server three
[01:10:05] saw command from also term three and the
[01:10:08] second slot the server one has nothing
[01:10:10] there at all and so question for this
[01:10:14] like the very first question is can this
[01:10:16] arrive could this setup arise and how
[01:10:21] yes
[01:11:02] so you know maybe server 3 was the
[01:11:04] leader for just repeating what you said
### chunk 91 [01:11:04]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

u know maybe server 3 was the
[01:11:04] leader for just repeating what you said[01:11:06] maybe server 3 is the leader for term 3
[01:11:08] he got a command that sent out to
[01:11:09] everybody everybody received a dependent
[01:11:11] at the log and then I got a server 3 got
[01:11:14] a second request from a client and maybe
[01:11:18] it sent it to all three servers but the
[01:11:19] message got lost on the way to server
[01:11:21] one or maybe server was down at the time
[01:11:23] or something and so only server to the
[01:11:25] leader always append new commands to its
[01:11:28] log before it sends out append entries
[01:11:29] and maybe the append entry RPC only got
[01:11:32] to server 2 so this situation you know
[01:11:34] it's like the simplest situation and was
[01:11:36] actually the logs are not different and
### chunk 92 [01:11:36]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

he simplest situation and was
[01:11:36] actually the logs are not different and[01:11:38] we know how it could possibly arise and
[01:11:43] so if server 3 which is a leadership
[01:11:45] crash now you know the next server
[01:11:46] they're gonna need to make sure server 1
[01:11:49] well first of all if server 3 crashes or
[01:11:54] we'll be at an election and some of the
[01:11:56] leader is chosen you know two things
[01:11:57] have to happen the new leader has got to
[01:12:00] recognize that this command could have
[01:12:04] committed it's not allowed to throw it
[01:12:06] away
[01:12:07] and it needs to make sure server one
[01:12:09] fills in this blank here with indeed
[01:12:12] this very same command that everybody
[01:12:13] else had in that slot all right so after
[01:12:17] a crash somebody you know server 3
### chunk 93 [01:12:17]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

ad in that slot all right so after
[01:12:17] a crash somebody you know server 3[01:12:20] suppose another way this can come up is
[01:12:22] server 3 might have sent out the append
[01:12:24] entries the server 2 but then crashed
[01:12:26] before sending the append entries to
[01:12:27] server 3 so if were you know electing a
[01:12:30] new leader it could because we got a
[01:12:32] crash before the message was sent
[01:12:34] here's another scenario to think about
[01:12:37] three servers again no I mean a number
[01:12:44] the slots in the law and so we can refer
[01:12:48] to them got slot 10 11 12 13
[01:12:55] [Music]
[01:12:57] again it's same setup except now we have
[01:13:04] in slide 12 we have server 2 as a
[01:13:07] command from term for and server 3 has a
[01:13:11] term command from term 5
[01:13:15] so you know before we analyze these to
### chunk 94 [01:13:15]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

3:11] term command from term 5
[01:13:15] so you know before we analyze these to[01:13:19] figure out what would happen and what
[01:13:21] would a server do if it saw this we need
[01:13:22] to ask could this even occur because
[01:13:24] sometimes the answer to the question oh
[01:13:27] jeez what would happen if this
[01:13:28] configuration arose sometimes the answer
[01:13:30] is it cannot arise so we do not have to
[01:13:32] worry about it the question is could
[01:13:37] this arise and how
[01:13:57] all right so any
[01:14:12] [Music]
[01:14:52] yeah
[01:14:59] in brief we know this configuration can
[01:15:02] arise and so the way we can then get the
[01:15:05] four and a five here is let's suppose in
[01:15:07] the next leader election server twos
[01:15:08] elected leader now for term for its
[01:15:11] elected leader because a request from a
### chunk 95 [01:15:11]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

d leader now for term for its
[01:15:11] elected leader because a request from a[01:15:13] client it appends it to its own log and
[01:15:15] crashes so now we have this right we
[01:15:20] need a new election because the leader
[01:15:21] just crashed now in this election and
[01:15:25] then so now we have to ask whether who
[01:15:27] could be elected or we have to give him
[01:15:29] back of our heads oh gosh what could be
[01:15:30] elected so we're gonna claim server
[01:15:32] three could be elected the reason why I
[01:15:34] could be elected is because it only
[01:15:35] needs request vote responses from
[01:15:38] majority that majority is server one and
[01:15:40] server three you know there's no no
[01:15:42] problem no conflict between these two
[01:15:44] logs so server three can be elected for
[01:15:46] term five get a request from a client
### chunk 96 [01:15:46]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

server three can be elected for
[01:15:46] term five get a request from a client[01:15:48] append it to its own log and crash and
[01:15:51] that's how you get this this
[01:15:54] configuration so you know you need to be
[01:15:57] able to to work through these things in
[01:16:04] order to get to the stage of saying yes
[01:16:05] this could happen and therefore raft
[01:16:07] must do something sensible as opposed to
[01:16:09] it cannot happen because some things
[01:16:11] can't happen
[01:16:17] all right so so what can happen now we
[01:16:23] know this can occur so hopefully we can
[01:16:27] convince ourselves that raft actually
[01:16:29] does something sensible now as for the
[01:16:34] range of things before we talk about
[01:16:36] what RAF would actually would actually
[01:16:39] do we need to have some sense of what
### chunk 97 [01:16:39]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

F would actually would actually
[01:16:39] do we need to have some sense of what[01:16:43] would be an acceptable outcome right and
[01:16:48] just eyeballing this we know that the
[01:16:53] command in slot 10 since it's known by
[01:16:55] all all the replicas it could have been
[01:16:59] committed so we cannot throw it away
[01:17:01] similarly the command in slot 11 since
[01:17:04] it's in a majority of the replicas it
[01:17:05] could for all we know have been
[01:17:06] committed so we can't throw it away the
[01:17:09] command in slot 12 however neither of
[01:17:11] them could possibly have been committed
[01:17:13] so we're entitled we don't know haven't
[01:17:16] we'll actually do but raft is entitled
[01:17:18] to drop both of these even though it is
[01:17:21] not entitled to drop it and either of
[01:17:23] the commands in a 10 or 11
### chunk 98 [01:17:23]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

:21] not entitled to drop it and either of
[01:17:23] the commands in a 10 or 11[01:17:26] this is entitled dropped it's not
[01:17:28] required to drop either one of them but
[01:17:31] I mean oh it certainly must drop one at
[01:17:33] least one because you have to have
[01:17:35] identical log contents in the end
[01:17:43] this could have been committed it the we
[01:17:47] can't tell by looking at the laws
[01:17:50] exactly how far the leader got before
[01:17:52] crashing so one possibility is that for
[01:17:55] this command or even this command one
[01:17:59] possibility is that leaders send out the
[01:18:00] append messages with a new command and
[01:18:02] then immediately crashed so it never got
[01:18:05] any response back because it crashed so
[01:18:08] the old leader did not know if it was
[01:18:09] committed and if it didn't get a
### chunk 99 [01:18:09]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

he old leader did not know if it was
[01:18:09] committed and if it didn't get a[01:18:12] response back that means it didn't
[01:18:14] execute it and it didn't send out but
[01:18:17] you know it didn't send out that
[01:18:18] incremented commit index and so maybe
[01:18:22] the replicas didn't execute it either so
[01:18:24] it's actually possible that this wasn't
[01:18:26] committed so even though RAF doesn't
[01:18:29] know it could be legal for raft
[01:18:35] if raft knew more than it does know it
[01:18:40] might be legal to drop this log entry
[01:18:43] because it might not have been committed
[01:18:45] but because on the evidence there's no
[01:18:48] way to disprove it was committed based
[01:18:51] on this evidence it could have been
[01:18:52] committed and raft can't prove it wasn't
[01:18:55] so it must treat it as committed because
### chunk 100 [01:18:55]
Lecture 6: Fault Tolerance: Raft (1) > Transcript

d raft can't prove it wasn't
[01:18:55] so it must treat it as committed because[01:18:58] the leader might have received it might
[01:19:01] have crashed just after receiving the
[01:19:03] append entry replies and replying to the
[01:19:05] client so just looking at this we can't
[01:19:08] rule out the possibility that either
[01:19:10] possibility that the leader responded to
[01:19:14] the client in which case we cannot throw
[01:19:15] away this entry because a client knows
[01:19:17] about it or the possibility the leader
[01:19:18] never did and yeah we could you know if
[01:19:23] we have to assume that it was committed
[01:19:33] yeah
[01:19:46] no there's no mañana server crash before
[01:19:51] getting the response it's alright well
[01:19:53] let's continue this on Thursday
