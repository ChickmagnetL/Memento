# System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra
- video_id: oYxTTirKY8M
- document_id: d903d515ad124b8999552c522aee0cd7
- platform: youtube
- duration: 7446s (124m06s)
- chunk_count: 189
- language_guess: en

## L3 brief
The text explains CSRF and XSS security vulnerabilities and concludes with a promotion for a system design mentorship program.

## L2 summary
This document section covers essential web security concepts, specifically focusing on how systems protect against common vulnerabilities like Cross-Site Request Forgery (CSRF) and Cross-Site Scripting (XSS). It explains that CSRF attacks are prevented using CSRF tokens combined with session cookies to block unauthorized requests from external domains. Additionally, it details how XSS attacks occur when malicious JavaScript is injected into user inputs and executed in other users' browsers. The passage concludes with an invitation for viewers to join the System Design Mastery mentorship program to learn full-stack system architecture and advance their engineering careers.

## Chunks
### chunk 0 [00:00]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

[00:00] AI is quickly changing software
[00:01] engineering. Almost every engineer
[00:03] nowadays uses AI to write the code
[00:06] implementation, and we're moving towards
[00:08] agentic development. And companies also
[00:11] know this, which is why they are now
[00:13] prioritizing different skills in
[00:15] interviews, not only whether you can
[00:17] write the code implementation, but
[00:19] whether you understand the system and
[00:21] trade-offs at the high level, which is
[00:23] why the best skill you can learn
[00:25] nowadays is system design, how all these
[00:28] components talk to each other high
[00:30] level, how to design them from scratch.
[00:32] So, in almost every tech interview, now
[00:36] there is a system design round where
### chunk 1 [00:36]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

in almost every tech interview, now
[00:36] there is a system design round where[00:37] they are testing your understanding on
[00:39] how systems actually work at the high
[00:41] level, and whether you can make
[00:44] architectural decisions at scale and
[00:46] articulate the trade-offs in systems you
[00:49] have built or worked on. And this is not
[00:52] only for interviews, even if you're not
[00:54] the one making all these decisions in
[00:56] your current role that you're working
[00:58] at, you still need to understand how the
[01:00] overall system functions, explain how
[01:03] components fit together in the system,
[01:05] and explain the trade-offs that were
[01:07] made while building the project. And
[01:10] that's exactly what we're going to cover
[01:12] in this full course. We're going to
[01:13] cover the skills that are proven at the
### chunk 2 [01:13]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

this full course. We're going to
[01:13] cover the skills that are proven at the[01:16] senior level and beyond. These are the
[01:18] exact skills and concepts that got me
[01:21] into senior and to lead engineer
[01:23] position, and also helped many engineers
[01:26] pass interviews at senior and staff
[01:28] level and land new roles. So, we're
[01:31] going to cover this in five steps.
[01:33] First, we'll start with the foundations,
[01:35] which are the core concepts every
[01:37] engineer should know. Then we'll get
[01:39] into API design, how to come up with
[01:41] contracts, versioning, and communication
[01:43] patterns, and design APIs from scratch.
[01:46] Then we'll get into databases, storage
[01:49] patterns, consistency, and when to use
[01:51] which type of database. Then we'll get
[01:53] into scaling, performance, caching,
### chunk 3 [01:53]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ich type of database. Then we'll get
[01:53] into scaling, performance, caching,[01:56] reliability, and handling points of
[01:58] failure in the system. And lastly, we'll
[02:01] cover interviews on how to pass these
[02:03] system design interviews that are coming
[02:05] up at almost every position that you
[02:08] apply nowadays, and how to prepare for
[02:11] those. Let's get started. Designing a
[02:13] system to support millions of users is
[02:15] challenging, but every complex system
[02:17] starts with something simple. That's why
[02:20] in this lesson, we'll build a basic
[02:21] setup that supports just one single
[02:23] user, and then we'll gradually expand it
[02:26] as we go. Because starting small allows
[02:28] us to understand each core component
[02:30] before adding more complexity. So, let's
[02:33] start with the first step and build a
### chunk 4 [02:33]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 adding more complexity. So, let's
[02:33] start with the first step and build a[02:34] single server setup. Imagine that we're
[02:37] setting up a system for a small user
[02:39] base. This means that everything runs on
[02:41] one single server. The web application,
[02:44] the database, the cache, and also the
[02:46] other components. And this setup allows
[02:49] us to visualize the core workings
[02:51] without added complexity. Now, let's
[02:53] break down how this single server setup
[02:55] handles the user requests. We have some
[02:58] users who are trying to access our
[03:00] website or our API on the server. They
[03:02] can be either using the web browser or a
[03:05] mobile app to access our server. And on
[03:08] the other hand, we have our server,
[03:09] which has the necessary files to serve
[03:11] to the web browsers and also the
### chunk 5 [03:11]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 which has the necessary files to serve
[03:11] to the web browsers and also the[03:13] necessary API endpoints to serve to the
[03:16] mobile app. And it is hosted on this
[03:18] example IP address. Initially, our users
[03:21] don't have this IP address. They have
[03:23] the domain which they're trying to
[03:24] access. Let's say it's app.demo.com.
[03:27] So, if they just type this domain name
[03:29] and hit enter, their web browser, for
[03:31] example, will contact a DNS, which
[03:33] stands for domain name system. This is a
[03:36] provider which maps the domains to the
[03:39] IP addresses. And in our case, let's say
[03:41] our domain name is mapped to the IP
[03:43] address, which is the server's IP
[03:45] address that we have. So, now this DNS
[03:48] provider will send the IP address back
[03:50] to the web browser or to the mobile app
### chunk 6 [03:50]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

er will send the IP address back
[03:50] to the web browser or to the mobile app[03:52] to our clients. And this IP address is
[03:55] our server's IP address. So, now they
[03:57] have the location where they are trying
[03:59] to send requests. So, with this IP
[04:01] address in hand, the user's device sends
[04:04] an HTTP request to our server asking for
[04:07] specific data. And then our server
[04:09] processes this request and sends back
[04:11] the requested data. This might be an
[04:14] HTML page for a browser or a JSON
[04:16] response for the app depending on the
[04:18] request type. In this setup, traffic
[04:21] usually originates from two main
[04:23] sources. The first one is the web
[04:25] applications and the second one is the
[04:27] mobile applications that are trying to
[04:29] access our server. For our web users,
### chunk 7 [04:29]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

le applications that are trying to
[04:29] access our server. For our web users,[04:32] the server handles the business logic,
[04:34] data storage, and also presentation
[04:36] using HTML, CSS, and JavaScript. And for
[04:39] mobile users, communication typically
[04:42] happens over HTTP. These mobile apps
[04:44] request data from the server using API
[04:47] calls, and JSON is often used for
[04:49] responses because it's lightweight and
[04:51] easy for mobile devices to interpret.
[04:54] Here is an example API request that we
[04:56] can receive for our server. It can be a
[04:58] get request to our domain {slash}
[05:00] product {slash} the ID of that product.
[05:03] And for this endpoint, we need to
[05:05] retrieve the details of a product. And
[05:07] here is an example response that we
[05:09] might send back to the client. This is a
### chunk 8 [05:09]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 is an example response that we
[05:09] might send back to the client. This is a[05:11] JSON response which contains the product
[05:13] ID. It contains the name of this
[05:15] product, some description, the price of
[05:18] the product, and some other metadata is
[05:21] useful for the client. And then this
[05:23] will be used by the mobile app or by the
[05:25] web browser to display this product on
[05:28] the screen. And as we continue, our goal
[05:30] will be to identify areas where a single
[05:32] server might not be enough for the user
[05:35] demand. For now, this setup is ideal for
[05:38] small user bases, but it may struggle
[05:40] under heavy traffic. So, next we'll
[05:42] explore ways to scale each part of the
[05:44] system to support more users
[05:46] effectively. Some key takeaways that we
[05:49] can have from this is that we need to
### chunk 9 [05:49]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

tively. Some key takeaways that we
[05:49] can have from this is that we need to[05:51] start small. We need to begin with a
[05:53] straightforward single server setup to
[05:55] understand the essential components of
[05:57] system architecture. Now, we also
[06:00] understand how these requests flow
[06:01] through your system, which is
[06:03] fundamental for building more scalable
[06:05] systems. And we also recognize the
[06:07] unique demands for web and mobile
[06:10] applications and how they interact with
[06:12] your server.
[06:13] And in the next lessons, we'll start
[06:15] looking at strategies for optimizing and
[06:17] scaling this setup. As our user base
[06:20] grows, a single server isn't enough to
[06:22] handle the increased demand. And to
[06:24] accommodate more users, we can separate
[06:26] our web tier, which is handling the web
### chunk 10 [06:26]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

date more users, we can separate
[06:26] our web tier, which is handling the web[06:29] and mobile traffic, and the data tier,
[06:31] which is managing the database. This
[06:33] setup enables us to scale each server
[06:36] based on its specific load. But when it
[06:38] comes to choosing the right database,
[06:40] how do we know which specific database
[06:42] is the best for our specific
[06:44] application? When it comes to database
[06:46] selection, there are two main options.
[06:48] The first option is relational databases
[06:51] or RDBMS, which are structured in tables
[06:53] and rows. Some popular examples are
[06:56] PostgreSQL, MySQL, Oracle database, or
[06:59] SQLite. On the other hand, we have
[07:01] non-relational or NoSQL databases. These
[07:04] are suited for applications that require
[07:07] flexibility and fast access to large
### chunk 11 [07:07]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

uited for applications that require
[07:07] flexibility and fast access to large[07:09] volumes of unstructured data. Some
[07:11] examples are Cassandra, MongoDB, Redis,
[07:15] or Neo4j. Let's start by exploring the
[07:17] relational databases. These databases
[07:20] use structured query language or SQL for
[07:23] finding and manipulating data. The data
[07:26] here is structured in tables, which are
[07:28] the fundamental building blocks of SQL
[07:30] databases. And these are similar to
[07:32] spreadsheets. Each table consists of
[07:34] columns, which can be thought as the
[07:36] fields or attributes of the table. And
[07:39] it also consists of rows, which are
[07:41] single records within this table. For
[07:43] example, if you imagine a customer's
[07:45] table, within this table we can have
[07:47] columns like ID, name, age, and email.
### chunk 12 [07:47]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

le, within this table we can have
[07:47] columns like ID, name, age, and email.[07:50] And for each rows, we can have specific
[07:52] customers like the ID of 123, and the
[07:55] name will be John, and the age will be
[07:57] 40, and so on. But what are the
[08:00] advantages of using an SQL database?
[08:02] First of all, they support complex join
[08:04] operations across multiple tables. For
[08:07] example, if you imagine we have a
[08:08] customer's table and also a product
[08:11] table. And now we want to create a
[08:13] separate table that will connect the
[08:15] customers and the products that they
[08:17] have ordered. With SQL, you can join
[08:20] these two tables together into an orders
[08:22] table, and this will hold the
[08:24] information about the customer IDs who
[08:26] have this order, and also the product
### chunk 13 [08:26]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

rmation about the customer IDs who
[08:26] have this order, and also the product[08:29] IDs which this customer has ordered. And
[08:31] this process of combining two or more
[08:34] tables into one table are called join
[08:36] operations in SQL. And the other big
[08:39] advantage is they provide robust data
[08:41] consistency and integrity, especially
[08:44] for transactions. Transactions in SQL
[08:46] are a sequence of one or more SQL
[08:49] operations that are performed as a
[08:51] single atomic unit, and each transaction
[08:53] in SQL follows the ACID acronym. You can
[08:56] think of a transaction example like a
[08:58] bank transfer. So first of all, all of
[09:00] the transactions are atomic, which means
[09:02] that the entire transaction is treated
[09:04] as a single unit, which either
[09:06] completely succeeds or completely fails.
### chunk 14 [09:06]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 as a single unit, which either
[09:06] completely succeeds or completely fails.[09:09] Each transaction is also consistent,
[09:11] which means that it transforms the
[09:12] database from one valid state to another
[09:15] valid state. And they also come with
[09:17] isolation, which means that
[09:19] modifications made by concurrent
[09:21] transactions are isolated from one
[09:23] another, and they don't interfere with
[09:25] each other. And lastly, they come with
[09:27] durability, which means even if the
[09:29] system fails or the database server
[09:31] fails, the data will still remain there.
[09:34] And now let's have a look at
[09:35] non-relational databases. Non-relational
[09:38] databases can be in different forms. For
[09:40] example, we have document stores like
[09:42] MongoDB, or you can use wide column
### chunk 15 [09:42]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

xample, we have document stores like
[09:42] MongoDB, or you can use wide column[09:44] stores like Cassandra, key-value stores
[09:47] like Redis, and graph stores like Neo4j.
[09:50] Let's have a look at each of these types
[09:52] separately, and let's start with the
[09:54] document stores. MongoDB is the most
[09:56] popular example of a document store, and
[09:59] the data here is stored in JSON-like
[10:01] documents, which allows us to have
[10:03] complex data structures within a single
[10:05] record. Next, we have wide column
[10:07] stores, where data is stored in tables,
[10:09] rows, and dynamic columns. Some examples
[10:12] here are Cassandra or Cosmos DB. The
[10:15] main advantage of these databases is
[10:17] they can handle massive scales and are
[10:19] very good for many write operations. The
[10:22] other option is graph databases, which
### chunk 16 [10:22]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

od for many write operations. The
[10:22] other option is graph databases, which[10:24] focus on storing the entities and their
[10:26] relationships as graphs. An example of a
[10:29] graph database is Neo4j. For example, in
[10:32] Amazon, they use the Neptune graph
[10:34] database, which helps them to make you
[10:36] product recommendations based on your
[10:38] previous orders. And the other popular
[10:41] type is key-value stores. Here, data is
[10:43] stored in key-value pairs. The biggest
[10:45] advantage of key-value stores is their
[10:47] simplicity and speed. Since they are
[10:50] primarily stored in RAM, reading and
[10:52] writing to these databases is extremely
[10:54] fast compared to other databases. Some
[10:57] examples of key-value stores are
[10:59] Memcached or Redis. So, that's the main
[11:01] four types of NoSQL databases. Now,
### chunk 17 [11:01]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

cached or Redis. So, that's the main
[11:01] four types of NoSQL databases. Now,[11:04] let's have a look at the advantages of
[11:06] these NoSQL databases. If you have a
[11:08] look at the same example that we had for
[11:10] the SQL databases, where we have
[11:12] customers and products, and we want to
[11:15] join them in orders. For example, in
[11:17] MongoDB, you could have this as a single
[11:19] document, so you could store all of the
[11:21] user data, also the orders and products
[11:24] in a single document. And because of
[11:26] this structure, the NoSQL databases can
[11:29] handle highly dynamic and large data
[11:31] sets without the structure imposed by
[11:33] relational databases. And also, they are
[11:36] optimized for low latency and
[11:38] scalability. So, when should you use
[11:40] relational versus non-relational
### chunk 18 [11:40]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

8] scalability. So, when should you use
[11:40] relational versus non-relational[11:42] databases? Here is a quick comparison of
[11:44] both. If your application data is
[11:46] well-structured with clear
[11:48] relationships, then you should use SQL
[11:50] databases. For example, if you have an
[11:52] e-commerce application tracking
[11:54] customers and orders, that's a good use
[11:57] case of using an SQL database. Next,
[12:00] need strong consistency and
[12:01] transactional integrity. For example, if
[12:04] you have a financial application or
[12:06] banking system, then you should use the
[12:08] SQL databases. However, if your app
[12:11] demands super low latency for quick
[12:13] responses, then you should go with
[12:15] non-relational databases. Or if the data
[12:17] is unstructured or semi-structured like
### chunk 19 [12:17]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

tional databases. Or if the data
[12:17] is unstructured or semi-structured like[12:20] JSON objects and the relationships
[12:22] aren't that crucial, then you should
[12:24] also go with no SQL databases. And
[12:26] lastly, if your application requires
[12:28] flexible and scalable storage for
[12:30] massive data volumes. For example, a
[12:32] recommendation engine storing user
[12:34] activity data and key value format, then
[12:37] you should also go with no SQL
[12:39] databases. Let's explore the two primary
[12:42] approaches to scaling, which are
[12:44] vertical and horizontal ways of scaling.
[12:47] And we'll also see why horizontal
[12:48] scaling is generally more suitable for
[12:51] high traffic applications. First, we
[12:53] have the vertical scaling or sometimes
[12:56] it's also called scale up. This just
### chunk 20 [12:56]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

e the vertical scaling or sometimes
[12:56] it's also called scale up. This just[12:58] means that we are adding more resources
[13:00] to our existing server, meaning RAM,
[13:03] CPU, or any other resources that might
[13:05] help us to handle more traffic. And this
[13:08] approach is simple and works well for
[13:10] applications that have low or moderate
[13:12] traffic. However, it comes with its
[13:15] limitations, which are firstly, resource
[13:18] limits. There is a hard cap on how much
[13:20] you can add to a single server. And
[13:23] eventually, you will reach a limit on
[13:25] how much you can upgrade your new
[13:27] server. And the second reason is lack of
[13:29] redundancy, meaning if this server goes
[13:32] down, you don't have any other servers
[13:34] to serve your users, which means that
[13:36] your whole application goes down with
### chunk 21 [13:36]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

serve your users, which means that
[13:36] your whole application goes down with[13:38] your single server.
[13:40] On the other hand, we have horizontal
[13:42] scaling, which is also sometimes called
[13:44] scale out. In case of horizontal
[13:46] scaling, we are just adding more servers
[13:49] to share the load. So, instead of having
[13:51] the single server, we might replicate
[13:53] and have three of that same server. And
[13:56] now we can share that load between these
[13:58] servers instead of handling all of them
[14:00] in a single server. Generally, this is
[14:02] more suitable for large-scale
[14:04] applications, as it comes with higher
[14:07] fault tolerance. And higher fault
[14:09] tolerance means if one of our servers
[14:11] goes down, we still have two servers
[14:13] available, so these two servers can
### chunk 22 [14:13]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

goes down, we still have two servers
[14:13] available, so these two servers can[14:15] continue serving our users while the
[14:17] second server recovers from the failure.
[14:20] And it also comes with better
[14:22] scalability, because you can just add
[14:24] more servers as needed. Instead of
[14:26] having three, you might introduce a
[14:28] fourth one, which will handle the new
[14:30] incoming traffic. But how do we
[14:32] implement the horizontal scaling? In
[14:34] case of a single server, we know that
[14:36] all of our client requests went to the
[14:38] single server, whether it's from mobile
[14:41] app or from the desktop. But what if now
[14:43] we have three servers to handle all the
[14:46] load? How do we distribute the client
[14:48] requests? Let's say our mobile app makes
[14:50] a request. How do we know where this
### chunk 23 [14:50]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

sts? Let's say our mobile app makes
[14:50] a request. How do we know where this[14:52] request should go? Whether it should go
[14:54] to the server one or server two or to
[14:57] server three? And seems like we need to
[14:59] have something in the middle, which will
[15:01] direct the traffic to the appropriate
[15:03] servers. And that part in the middle is
[15:06] called a load balancer. We use load
[15:09] balancers to distribute the traffic
[15:11] across multiple servers. For example,
[15:13] here we have three servers, server one,
[15:16] two, and three.
[15:17] Whenever we have a new request from the
[15:19] clients, the load balancer decides where
[15:22] we have the least load and then it
[15:24] redirects the traffic to that server.
[15:26] And it also controls the fault
[15:28] tolerance, meaning if one of our server
### chunk 24 [15:28]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

] And it also controls the fault
[15:28] tolerance, meaning if one of our server[15:30] goes down, like the server free, it will
[15:33] stop sending traffic to the first server
[15:35] since it's not available anymore and it
[15:37] will send all of the traffic to server
[15:40] two and one until the server free is
[15:42] available again. And it also can make
[15:45] our app more scalable because we can
[15:47] introduce a new fourth server and any
[15:49] other servers that we want and this load
[15:52] balancer will ensure that all of the
[15:54] traffic is distributed evenly. So,
[15:56] that's the two main approaches of
[15:58] scaling, which are vertical and
[16:00] horizontal ways of scaling. In case of
[16:02] vertical scaling, we are just adding
[16:04] more resources to our same server, but
[16:07] in case of horizontal scaling, we are
### chunk 25 [16:07]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 resources to our same server, but
[16:07] in case of horizontal scaling, we are[16:09] adding more users to our server base and
[16:12] then we use a load balancer which
[16:14] distributes the traffic across multiple
[16:16] servers. But right now this load
[16:18] balancer is kind of a black box for us
[16:21] because we don't understand how does it
[16:23] work, how does it take the requests and
[16:25] how does it distribute the traffic. So,
[16:28] let's explore that in the next lesson
[16:30] and let's see how this exactly works and
[16:32] what are the strategies that we use in
[16:34] load balancing. Load balancers
[16:36] distribute the incoming traffic across
[16:38] multiple servers while also ensuring
[16:41] that no single server bears too much
[16:43] load, but how does it actually happen
[16:45] and how does the logic work of
### chunk 26 [16:45]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

43] load, but how does it actually happen
[16:45] and how does the logic work of[16:47] distributing the incoming traffic? To
[16:50] understand load balancers better, let's
[16:52] explore seven strategies and algorithms
[16:55] that are commonly used in load
[16:57] balancing.
[16:58] Let's start with round robin, which is
[17:00] one of the most popular algorithms.
[17:02] That's mainly because it's the simplest
[17:04] form of load balancing where each
[17:06] servers in the pool gets a request in
[17:09] sequential rotating order, which
[17:11] basically means that the first request
[17:13] that it receives, it directs it to the
[17:16] first server and the next request will
[17:18] go to the second server, and the third
[17:20] one will go to the fourth server.
[17:23] And once the last server is reached, in
[17:25] this case it's the server three, it
### chunk 27 [17:25]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 once the last server is reached, in
[17:25] this case it's the server three, it[17:28] redirects it back to the first server,
[17:30] and then again to the second server, and
[17:32] so on.
[17:33] This works well for servers with similar
[17:35] specifications, meaning if all of our
[17:38] three servers have the same capability,
[17:40] then round robin will be a good choice
[17:43] here.
[17:44] Next option is the least connections
[17:46] algorithm. It directs traffic to the
[17:48] server with the fewest active
[17:50] connections. For example, if we have 10
[17:53] active connections on the server one, we
[17:55] have nine active connections on the
[17:57] server two, and we have 30 active
[17:59] connections on the server three.
[18:02] If it receives a new request from the
[18:04] client, it will direct it to the server
### chunk 28 [18:04]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 receives a new request from the
[18:04] client, it will direct it to the server[18:06] two because it has the least active
[18:08] connections at the moment. So, now it
[18:11] will have one more connection. And this
[18:13] is particularly useful for applications
[18:15] where you have sessions of variable
[18:17] lengths, meaning that one of your
[18:19] sessions might last 10 minutes, the
[18:21] other one might last one minute, and so
[18:23] on. And in this case, the load balancer
[18:25] will take that into account, and it will
[18:28] send the traffic to the least connection
[18:30] server. The third option is least
[18:32] response time.
[18:34] This algorithm is more focused on
[18:36] responsiveness of the servers.
[18:38] Let's say your first server is highly
[18:40] responsive, the second one is low
[18:42] responsiveness, and the third one is
### chunk 29 [18:42]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

] responsive, the second one is low
[18:42] responsiveness, and the third one is[18:44] medium responsiveness.
[18:46] In that case, the load balancer chooses
[18:48] the lowest response time, and with the
[18:51] fewest active connections. Meaning first
[18:53] it will try to send as many connections
[18:55] to the high responsive server as
[18:57] possible, but it also takes into account
[19:00] the active connections. Let's say this
[19:02] server reaches 40 active connections,
[19:05] then it will switch to the third server
[19:07] because this is the medium
[19:08] responsiveness server, and it will send
[19:10] some traffic, let's 20 other requests to
[19:13] the medium responsiveness server. And
[19:15] after that, it will switch to the second
[19:17] server, and it might send another 10
[19:19] requests to this fourth server until it
### chunk 30 [19:19]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

er, and it might send another 10
[19:19] requests to this fourth server until it[19:22] redirects them back to the first server.
[19:25] This is effective when the goal is to
[19:26] provide the fastest response time to
[19:29] requests, and you also have different
[19:31] servers with different capabilities.
[19:34] The fourth option is the IP hash
[19:36] algorithm, which determines which server
[19:38] receives the request based on the hash
[19:40] of the client's IP address. This is
[19:43] useful when you want your clients to
[19:45] consistently connect to the same server.
[19:47] Let's say client one makes a request to
[19:49] your load balancer.
[19:51] The load balancer will use the client's
[19:53] IP address, and based on this, it will
[19:55] hash it and send it to appropriate
[19:57] server, let's say server two. And all of
### chunk 31 [19:57]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

h it and send it to appropriate
[19:57] server, let's say server two. And all of[20:00] the future requests of the client one
[20:02] will go to the load balancer, and it
[20:04] will use the same IP hashing algorithm,
[20:07] and based on this IP address, it will
[20:09] again redirect the user one requests to
[20:11] the server two. This is useful if it's
[20:14] important for a client to consistently
[20:16] connect to the same application.
[20:19] If every of your server has some
[20:21] information about the clients that are
[20:23] connected to it, in that case, the IP
[20:25] hashing is a good choice.
[20:27] Then, there are also weighted
[20:28] algorithms. These are variants of the
[20:31] above methods that can be also weighted.
[20:33] For example, you can have a weighted
[20:35] round robin or weighted least
[20:37] connections.
### chunk 32 [20:35]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

u can have a weighted
[20:35] round robin or weighted least
[20:37] connections.[20:38] In this case, servers are assigned two
[20:40] weights, typically based on their
[20:42] capacity and performance metrics.
[20:45] For example, if the first server has 16
[20:47] gigs of RAM, the second one has 32, and
[20:50] the third one has 64,
[20:53] based on the server RAM and other
[20:55] metrics, they are assigned two weights,
[20:57] and the load balancer takes that into
[20:59] account when redirecting the traffic.
[21:01] First, it will try to send as many
[21:03] connections to the first server as
[21:05] possible because it's more weighted,
[21:07] meaning it has more performance, and
[21:10] then it will try to send the other
[21:11] traffic to server two, and then the last
[21:14] and small portion will go to server one.
### chunk 33 [21:14]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

o server two, and then the last
[21:14] and small portion will go to server one.[21:17] There are also geographical algorithms,
[21:19] which are location-based algorithms that
[21:22] direct requests to the server
[21:24] geographically closest to the user.
[21:26] Let's say this application is for US
[21:29] users, so mostly users are connecting to
[21:31] this application from US, but we also
[21:34] have some part of the users who are
[21:35] connecting from Europe. And in our pool
[21:38] of servers, we can have one server that
[21:40] is located in US East, another server
[21:43] that is located in US West, and the last
[21:46] server can be located somewhere in
[21:48] Europe for the small base of users who
[21:50] are located in Europe. So, if a user
[21:53] comes from Europe and makes a request to
[21:55] this load balancer, it will redirect
### chunk 34 [21:55]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 from Europe and makes a request to
[21:55] this load balancer, it will redirect[21:57] this user to the server in Europe. Or if
[22:00] a user comes from your US and makes a
[22:02] request to this load balancer, it will
[22:04] check the location of this US user based
[22:07] on its IP address, and then it will
[22:09] redirect either to the US East or US
[22:11] West. This type of load balancing is
[22:14] useful for global services where latency
[22:17] reduction is important. And the last
[22:19] most popular type is consistent hashing.
[22:22] In this case, we use a hash function to
[22:24] distribute data across various nodes.
[22:27] We have a hash function inside of a load
[22:29] balancer, and we usually imagine a hash
[22:32] space along with this that forms a hash
[22:34] ring, like a circle.
[22:36] This hash function forms a circle where
### chunk 35 [22:34]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ash
[22:34] ring, like a circle.
[22:36] This hash function forms a circle where[22:38] we have the servers, for example, the
[22:40] server one, two, and three, which are
[22:43] located in front of this load balancer.
[22:46] So, whenever a new request comes from a
[22:48] user, this hash function takes the IP
[22:50] address of that user, and then based on
[22:53] that, it locates this user on this hash
[22:55] ring. Let's say it locates it somewhere
[22:57] here, and then depending to which server
[23:00] this point is closest to, for example,
[23:02] in this case this is closer to server
[23:04] two, it redirects the traffic to that
[23:07] server.
[23:08] This is a bit more complicated way of
[23:10] load balancing, but it also ensures that
[23:12] the same client consistently connects to
[23:15] the same server like in case of IP
[23:17] hashing.
### chunk 36 [23:15]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

istently connects to
[23:15] the same server like in case of IP
[23:17] hashing.[23:18] We also talked about that whenever a
[23:20] server goes down, this load balancer
[23:22] ensures that traffic is not redirected
[23:24] to that server.
[23:26] But how does it know in the first place
[23:28] that this server is not available? For
[23:30] that most load balancers come with
[23:32] health check features, which means that
[23:35] they are consistently monitoring the
[23:36] servers by sending a health check
[23:39] requests to all of these servers, and
[23:41] they have the information about which
[23:43] servers are online. Let's say the first
[23:45] three servers are available, and which
[23:47] ones are offline, which means the fourth
[23:49] server, which is offline.
[23:51] So whenever it detects a failure in the
[23:54] health check, it knows that this fourth
### chunk 37 [23:54]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ever it detects a failure in the
[23:54] health check, it knows that this fourth[23:56] server is not available anymore, and
[23:58] based on that information, if the next
[24:01] request comes from the client, it won't
[24:03] redirect them to the fourth server until
[24:06] the health check again succeeds, and it
[24:08] knows that the fourth server is back
[24:10] online.
[24:11] And now let's see some load balancer
[24:13] examples, and what are these actually?
[24:15] How do we implement them? First we have
[24:17] software load balancers. For example,
[24:20] Nginx is probably the most common type
[24:22] of the software load balancer.
[24:25] It has other features, and it's also
[24:27] used as a web server, but it also offers
[24:29] the functionality of balancer.
[24:32] Typically you install this Nginx on your
[24:34] server, and then configure the servers
### chunk 38 [24:34]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ly you install this Nginx on your
[24:34] server, and then configure the servers[24:37] that should be load balanced, and also
[24:39] the algorithm. And as you can see it
[24:41] also comes with health checks, which I
[24:43] mentioned. So you can set up health
[24:45] checks among your servers, and then this
[24:47] will consistently monitor your servers,
[24:49] and whenever one of your server goes
[24:51] down, it won't redirect traffic to that
[24:53] server.
[24:55] Another example of a software load
[24:57] balancer is HAProxy, which is an open
[24:59] source software that again you can
[25:01] install on your server and configure as
[25:03] you want. But apart from software load
[25:06] balancers, we also have hardware load
[25:08] balancers. For example, we have the F5
[25:11] load balancer, which is a widely used
[25:13] hardware load balancer known for its
### chunk 39 [25:13]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ad balancer, which is a widely used
[25:13] hardware load balancer known for its[25:15] high performance and feature set.
[25:18] Next, we have Citrix, which also comes
[25:20] with load balancing functionality. And
[25:23] again, this is a hardware type of load
[25:25] balancer.
[25:26] But if you don't want to configure all
[25:28] of that yourself on your server or as a
[25:30] hardware, then the easier solutions are
[25:32] cloud-based load balancers. For example,
[25:35] AWS comes with elastic load balancing.
[25:38] And if you have your servers also set up
[25:40] in AWS, then it's pretty easy to
[25:42] configure this with your servers. And
[25:45] you can also see it in the benefits that
[25:47] it automatically comes with security,
[25:49] automatic scaling, meaning that it will
[25:51] automatically add new servers to the
### chunk 40 [25:51]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

matic scaling, meaning that it will
[25:51] automatically add new servers to the[25:53] pool if the demand increases of your
[25:55] application. And it also comes with
[25:57] monitoring, which is the same as health
[25:59] checks. So you don't have to set it up
[26:02] yourself. And other examples similar to
[26:04] AWS are Azure's load balancer and Google
[26:07] Cloud's load balancing. Now, let's talk
[26:10] about the concept which is called a
[26:12] single point of failure in system
[26:14] design. This is one part of your whole
[26:16] system that whenever it fails, it will
[26:19] bring the entire system down with it. So
[26:22] to put it simply, it is any component
[26:24] that could cause the whole system to
[26:27] fail whenever it stops working. For
[26:30] example, if you imagine this setup when
[26:32] the clients connect to our load balancer
### chunk 41 [26:32]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 if you imagine this setup when
[26:32] the clients connect to our load balancer[26:35] and then load balancer distributes them
[26:37] to the APIs, and then we have a single
[26:39] database which is used for all API
[26:42] servers. Database here is one example of
[26:46] a single point of failure. Whenever this
[26:48] database goes down, all of these APIs
[26:50] won't be able to connect to the database
[26:53] and because of that all of these also
[26:55] won't function properly and our clients
[26:58] won't be able to receive any response
[27:00] from the servers. So, having single
[27:03] points of failures in your system is
[27:05] problematic because they can create
[27:07] vulnerabilities.
[27:09] The first obvious downside is the
[27:10] reliability because a single failure
[27:13] like the failure of this database can
### chunk 42 [27:13]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

liability because a single failure
[27:13] like the failure of this database can[27:15] take the entire system down which could
[27:18] mean business losses because users are
[27:20] not able to access our platform. Maybe
[27:22] they are also not able to access the
[27:24] checkout page or any other parts of the
[27:27] system which can bring losses in the
[27:29] business.
[27:31] It is also an issue for scalability
[27:33] because systems that have single point
[27:35] of failures like this can often struggle
[27:38] to scale as each component will add a
[27:40] risk of failing this single part.
[27:43] And the last part it also brings a
[27:45] security issue because if you have a
[27:47] single point of failure in your system
[27:49] like the load balancer, attackers can
[27:52] compromise this point by sending huge
[27:54] traffic to it and if this fails, the
### chunk 43 [27:54]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

mpromise this point by sending huge
[27:54] traffic to it and if this fails, the[27:56] whole system will go down.
[27:58] We will talk about how to avoid the
[28:00] database single points of failure in the
[28:03] databases section, but in this section
[28:05] we can have a look at how to avoid the
[28:07] load balancers to become a single point
[28:10] of failure because right now we have
[28:12] only one load balancer setup. And if
[28:15] this load balancer goes down, then all
[28:17] of our users won't be able to access
[28:19] this point and they will also not be
[28:21] able to access to our APIs.
[28:24] The first strategy is adding redundancy
[28:27] to our system. This means that we can
[28:29] use more than one load balancer and for
[28:31] example, if the second load balancer
[28:33] goes down, users won't be able to
### chunk 44 [28:33]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

] example, if the second load balancer
[28:33] goes down, users won't be able to[28:35] connect to this load balancer, but in
[28:38] that case we can redirect all of the
[28:40] traffic to the first one and then this
[28:42] first load balancer will balance the
[28:44] load between those servers and we will
[28:47] monitor the health of the second load
[28:49] balancer and whenever it's back online
[28:52] and it's again available, we will also
[28:54] redirect 50% of the traffic to the
[28:57] second load balancer.
[28:59] Another strategy is to use health checks
[29:01] and monitoring for load balancers
[29:03] themselves. As we saw load balancer can
[29:06] do health checks for the servers and
[29:08] check whenever our servers are online or
[29:11] offline. We can do the same strategy for
[29:14] load balancers and we can check their
### chunk 45 [29:14]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

e. We can do the same strategy for
[29:14] load balancers and we can check their[29:15] health continuously and whenever one of
[29:18] our load balancer goes down, we will
[29:20] know that we shouldn't redirect any
[29:22] traffic to this load balancer until it
[29:24] is back online. And the third common
[29:27] type is self-healing systems, which
[29:30] means that we again monitor the health
[29:32] of our load balancer and if at any point
[29:35] we detect that it goes down, we will
[29:37] replace this with a new load balancer,
[29:39] which is basically an instance of the
[29:41] same load balancer and this way we won't
[29:44] cause any interruptions and our clients
[29:46] will be able to connect to this new load
[29:49] balancer. Welcome to this section where
[29:51] you will learn the fundamental
[29:53] principles of API design, which will
### chunk 46 [29:53]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

:51] you will learn the fundamental
[29:53] principles of API design, which will[29:55] enable you to create efficient, scalable
[29:58] and also maintainable interfaces between
[30:01] software systems. Here is what we're
[30:03] going to cover in this lesson. We'll
[30:05] start from what APIs are and what is
[30:08] their role in system architecture. Then
[30:10] we'll cover the three most commonly used
[30:13] API styles, which are REST, GraphQL and
[30:16] gRPC. We'll discuss the four essential
[30:19] design principles that make great APIs
[30:22] and also how application protocols
[30:24] influence the API design decisions.
[30:27] We'll also cover the API design process,
[30:30] so starting from the design phase to
[30:32] development phase to deployment, so
[30:34] we'll see how that process looks like.
[30:37] So let's start by understanding what is
### chunk 47 [30:37]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

see how that process looks like.
[30:37] So let's start by understanding what is[30:38] an API. API stands for application
[30:41] programming interface, which defines how
[30:43] software components should interact with
[30:46] each other.
[30:47] Let's say on one side you have the
[30:48] client, which is either the mobile phone
[30:50] or the browser of this user, and on the
[30:53] other side you have the server, which
[30:55] will be responding to the requests.
[30:57] So, API here is just a contract that
[31:00] defines these terms, which are what
[31:02] requests can be made. So, it provides us
[31:04] with an interface on how to make these
[31:06] requests, meaning what endpoints do we
[31:09] have, what methods can we use, and so
[31:11] on. Also, what responses can we expect
[31:14] from the server for a specific endpoint.
### chunk 48 [31:14]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

o, what responses can we expect
[31:14] from the server for a specific endpoint.[31:18] So, first of all, it is an abstraction
[31:20] mechanism because it hides the
[31:22] implementation details while exposing
[31:24] the functionality. For example, we can
[31:27] make a request to save a user data in
[31:29] this server, but we don't care at all
[31:32] about how the logic applies behind the
[31:34] scenes inside of this server. So, we
[31:36] only care about the interface that is
[31:38] provided through this API, and we only
[31:41] use that endpoint, and we store the user
[31:44] without even knowing about the
[31:45] implementation details. And it also sets
[31:48] the service boundaries because it
[31:51] defines clear interfaces between systems
[31:53] and components. So, this allows us to
[31:55] have multiple servers. We can have one
### chunk 49 [31:55]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

components. So, this allows us to
[31:55] have multiple servers. We can have one[31:58] server that is responsible for managing
[32:00] the users. We can have another one that
[32:02] is responsible for some other records,
[32:04] let's say for managing the posts, and so
[32:07] on.
[32:08] So, this allows different systems to
[32:10] communicate regardless of their
[32:12] underlying implementation, like client
[32:15] browsers with servers or servers with
[32:17] another servers, and so on.
[32:19] Now, let's focus on the most important
[32:21] API styles you will encounter during the
[32:24] design phase. These are RESTful,
[32:26] GraphQL, and gRPC. The most common one
[32:29] out of these is REST, which stands for
[32:32] representational state transfer. These
[32:35] type of APIs use resource-based approach
[32:37] by using the HTTP methods as a protocol.
### chunk 50 [32:37]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

PIs use resource-based approach
[32:37] by using the HTTP methods as a protocol.[32:41] One of the advantages of REST APIs is
[32:44] that they are stateless, meaning that
[32:46] each request contains all of the
[32:47] information needed to process it, and we
[32:49] don't need any prior requests to be able
[32:52] to process the current request. And it
[32:55] uses the standard methods on HTTP
[32:57] protocol, which are get for fetching
[32:59] data, post for storing data, put or
[33:02] patch for updating data, and delete for
[33:05] deleting data.
[33:07] So, based on its characteristics, the
[33:09] REST is most commonly used in web and
[33:12] mobile applications. Next, we have
[33:14] GraphQL, which is the second most common
[33:16] API style after the REST APIs. GraphQL
[33:20] is a query language that allows clients
### chunk 51 [33:20]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

yle after the REST APIs. GraphQL
[33:20] is a query language that allows clients[33:22] to request exactly what they need. This
[33:25] means that it comes with a single
[33:27] endpoint for all of the operations, and
[33:30] we can choose what we are expecting to
[33:32] receive from this API by providing the
[33:34] payload in the request.
[33:36] And the operations here are called query
[33:39] whenever we are retrieving data, or
[33:41] mutation whenever we are updating data.
[33:44] So, this is the equivalent in put or
[33:46] patch or post in the RESTful APIs. And
[33:50] there is also a subscription in
[33:52] operations, which is for real-time
[33:54] communication. The advantage of GraphQL
[33:56] APIs is that it allows us to have
[33:58] minimal round trips. Let's say we need
[34:01] some data that in RESTful APIs we will
### chunk 52 [34:01]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

al round trips. Let's say we need
[34:01] some data that in RESTful APIs we will[34:03] need to make three requests to get all
[34:06] of this data.
[34:07] In GraphQL case, we can make a single
[34:09] request and get all of this data,
[34:11] avoiding the unnecessary two requests
[34:14] that we will otherwise have to make in
[34:16] RESTful.
[34:17] And because of that, this is the
[34:18] recommended option for complex UIs. So,
[34:21] wherever you have some complex UIs where
[34:23] on one page you might need different
[34:25] data, on another page you might need
[34:27] some other complex nested data. In these
[34:30] cases, GraphQL is the better choice over
[34:32] RESTful APIs.
[34:34] And the last option is gRPC. I would say
[34:36] this is the least common one out of
[34:38] these three.
[34:40] gRPC is a high-performance RPC
### chunk 53 [34:38]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

st common one out of
[34:38] these three.
[34:40] gRPC is a high-performance RPC[34:42] framework, which is using protocol
[34:45] buffers for communication.
[34:47] The methods in gRPC are defined as RPCs
[34:51] in the proto files, and it supports
[34:54] streaming and bidirectional
[34:55] communication. This is an excellent
[34:58] approach for microservices especially
[35:00] and internal system communication, as it
[35:03] is more efficient when you're working
[35:05] between servers compared to GraphQL or
[35:07] compared to RESTful APIs.
[35:10] So, the difference between REST,
[35:12] GraphQL, and gRPC APIs is kind of clear,
[35:15] but let's also clarify the real
[35:17] difference between REST and GraphQL APIs
[35:19] on examples.
[35:21] So, as you saw, REST comes with
[35:23] resource-based endpoints. For example,
[35:25] here, if we take a look at these
### chunk 54 [35:25]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 resource-based endpoints. For example,
[35:25] here, if we take a look at these[35:26] requests, you can see that the resource
[35:28] here is users. So, you always expect to
[35:31] see some users endpoint or some
[35:34] followers endpoint or, let's say, posts
[35:36] endpoint. So, it is resource-based.
[35:39] And sometimes we might need to make
[35:40] multiple requests for getting the
[35:42] related data. As you can see here, we
[35:45] need, let's say, the user details, but
[35:47] we also need the user posts and
[35:49] followers. So, in this case, we need to
[35:51] make three requests to get all of these
[35:53] data.
[35:54] And it uses HTTP methods to define
[35:57] operations. As you can see, these are
[35:59] HTTP endpoints, and we are using the get
[36:02] method specifically. And the response
[36:04] structures are fixed, meaning if you got
### chunk 55 [36:04]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 specifically. And the response
[36:04] structures are fixed, meaning if you got[36:06] one response for this specific user,
[36:09] next time you can expect to have exactly
[36:11] the same response structure. Maybe some
[36:13] data will be modified, but the structure
[36:16] always remains the same. And it also
[36:18] provides explicit versioning. So, as you
[36:20] can see, it comes with V1 for the V1
[36:23] API. Then later, if it got a major
[36:25] upgrade, then this will become V2, and
[36:28] so on. And you can use the headers on
[36:30] the requests to leverage the HTTP
[36:33] caching on RESTful APIs. Now, if we
[36:36] compare that to GraphQL APIs, it comes
[36:38] with a single endpoint for all
[36:40] operations. So, mostly it is {slash}
[36:43] GraphQL or {slash} some API endpoint
[36:46] that is commonly used for all
### chunk 56 [36:46]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

6:43] GraphQL or {slash} some API endpoint
[36:46] that is commonly used for all[36:48] operations. And in this case, we will
[36:50] use a single request to get the precise
[36:52] data that we need, and we will use the
[36:55] query language of GraphQL.
[36:57] This is what the query language looks
[36:59] like. As you can see, we start with a
[37:01] query, and then we define what we need.
[37:03] For example, we need the user with ID
[37:05] 123. Then we need the name of the user,
[37:09] the posts, and then we define whatever
[37:11] we need from the posts. Maybe we need
[37:13] only title and content, and nothing
[37:15] more. And also the followers, and what
[37:18] we need from followers, maybe only
[37:20] names. So, this allows us to be more
[37:22] efficient in our requests compared to
[37:25] RESTful APIs, where we will need to make
### chunk 57 [37:25]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ent in our requests compared to
[37:25] RESTful APIs, where we will need to make[37:27] three requests for this same data.
[37:30] This means that client needs to specify
[37:32] the response structure. And in this
[37:35] case, the schema evolution is without
[37:37] versioning. So, here as you saw, it is
[37:39] with V1, V2, and so on. In this case,
[37:42] the schema usually evolves without
[37:44] versioning, but there is also a common
[37:46] pattern to start versioning the fields.
[37:49] For example, you can have followers V2,
[37:52] and that will be the second type of
[37:55] followers schema. But you can also go
[37:58] without versioning, so you can just
[37:59] start modifying the followers or posts
[38:02] if you are sure that there are no other
[38:04] clients using your old API.
[38:07] And in this case, you can leverage the
### chunk 58 [38:07]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

8:04] clients using your old API.
[38:07] And in this case, you can leverage the[38:09] application-level caching instead of the
[38:11] HTTP caching.
[38:13] Now, let's discuss the major design
[38:15] principles that will allow us to create
[38:18] consistent, simple, secure, and also
[38:20] performant APIs.
[38:22] Ultimately, the best API is the one that
[38:25] we can use without even reading the
[38:27] documentation. For example, if you saw
[38:29] the previous endpoints in the users, you
[38:32] see that we have {slash} users {slash}
[38:34] 123, and obviously we are expecting to
[38:37] get the user details of this specific
[38:40] user. And if you make a request, for
[38:42] example, to that endpoint to fetch user
[38:44] details, but then you find out that it
[38:46] also update some followers or something
[38:49] while making this request, then
### chunk 59 [38:49]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 also update some followers or something
[38:49] while making this request, then[38:51] obviously that is a very bad type of API
[38:54] as we didn't expect it to do such
[38:56] operations.
[38:57] So, first of all, the good API should be
[38:59] consistent, meaning it should use the
[39:02] consistent naming, casing, and patterns.
[39:05] For example, if you use camel case in
[39:07] one of the endpoints, let's say you have
[39:09] user details, and you do this in camel
[39:12] case, but in another case you do it with
[39:15] a snake case like user {slash} details,
[39:18] then this is not common and this is not
[39:20] consistent.
[39:22] The second key principle is to keep it
[39:24] very simple and focus on core use cases
[39:27] and intuitive design.
[39:29] So, you should minimize complexity and
[39:32] aim for designs that developers can
### chunk 60 [39:32]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

, you should minimize complexity and
[39:32] aim for designs that developers can[39:34] understand quickly without even maybe
[39:36] reading the documentation. And
[39:38] simplicity again comes down to this,
[39:40] which is the best API is one that
[39:43] developers can use without even reading
[39:45] the documentation.
[39:47] Next, obviously it has to be secure, so
[39:49] you have to have some sort of
[39:50] authentication and authorization between
[39:53] users. Also, if you have inputs, then
[39:55] you need to make sure that these are
[39:57] validated, and you should also apply
[39:59] rate limiting. So, these are the most
[40:02] basic things that you have to do to keep
[40:04] your APIs secure.
[40:06] And the last pillar is performance, so
[40:09] you should design for efficiency with
[40:11] appropriate caching strategies, with
### chunk 61 [40:11]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

u should design for efficiency with
[40:11] appropriate caching strategies, with[40:13] pagination. If you have a large amount
[40:16] of data, let's say thousands of posts,
[40:19] you don't want to retrieve all of these
[40:20] whenever they make a request to get the
[40:23] posts. So, you should always have
[40:24] pagination with some limit and offset.
[40:27] Also, the payloads, meaning the data
[40:29] that you will send back, should be
[40:31] minimized. And also, whenever possible,
[40:33] you should reduce the round trips. So,
[40:36] if you have the opportunity to send some
[40:38] small data along with the request of one
[40:41] of the endpoints, then it's better to do
[40:43] this if you know that you're going to
[40:45] use it instead of making another
[40:47] endpoint for making a request to get the
[40:49] same data.
### chunk 62 [40:47]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

king another
[40:47] endpoint for making a request to get the
[40:49] same data.[40:51] Now, each of these APIs use different
[40:53] protocols, and we will learn more about
[40:56] these in the next lesson. But,
[40:58] basically, your protocol choice will
[41:00] fundamentally shape your API design
[41:02] options. For example, the features of
[41:05] HTTP protocol directly enable RESTful
[41:08] capabilities. So, it makes more sense to
[41:10] use HTTP along with RESTful APIs because
[41:14] it also provides you with status codes,
[41:16] and these are great to be used with CRUD
[41:19] operations that you will have in RESTful
[41:21] APIs.
[41:22] On the other hand, WebSockets, which is
[41:24] another type of protocol, enable
[41:27] real-time data and also enable
[41:29] bidirectional APIs. So, these can be
[41:31] used along with real-time APIs wherever
### chunk 63 [41:31]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

rectional APIs. So, these can be
[41:31] used along with real-time APIs wherever[41:34] you need some chat application or some
[41:36] video streaming. This is a good use case
[41:39] of WebSocket APIs.
[41:41] In case of GraphQL APIs, you again will
[41:43] use the HTTP protocol instead of
[41:46] WebSockets or gRPC.
[41:48] gRPC, on the other hand, can be used
[41:51] among with microservices in your
[41:53] architecture to make it faster compared
[41:56] to HTTP.
[41:57] So, your protocol choice will affect the
[41:59] API structure and also the performance
[42:02] and capabilities.
[42:04] Therefore, you should choose it based on
[42:06] its limitations and strengths, and the
[42:08] one that makes more sense in the type of
[42:11] API that you'll be developing.
[42:14] Now, let's discuss the API design
[42:16] process. It all starts with
### chunk 64 [42:14]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

g.
[42:14] Now, let's discuss the API design
[42:16] process. It all starts with[42:17] understanding the requirements, which is
[42:20] identifying core use cases and user
[42:22] stories that you will need to develop.
[42:25] Also, defining the scope and boundaries
[42:27] because if it's a huge API, then you
[42:30] probably won't develop all of the
[42:32] features at once. So, you should scope
[42:34] it to some specific features that you'll
[42:37] be developing and also what are out of
[42:39] scope for now. Then you should determine
[42:42] the performance requirements and
[42:44] specifically in your API case, what will
[42:46] be the bottlenecks and where you need to
[42:48] make sure that it's performant.
[42:51] And you should also not overlook the
[42:53] security constraints. So, you should
[42:55] implement all of the basic features like
### chunk 65 [42:55]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ity constraints. So, you should
[42:55] implement all of the basic features like[42:57] authentication, authorization, the rate
[43:00] limiting, but maybe some more stuff
[43:02] depending on the API that you'll
[43:04] develop. When it comes to design
[43:06] approaches, there are couple of ways to
[43:08] go about it. The first one is top-down
[43:10] approach, which is you start with
[43:12] high-level requirements and workflows.
[43:15] This is more common in interviews where
[43:17] they give you the requirements on what
[43:19] the API will be about, and then you
[43:22] start defining what the endpoints will
[43:24] be, what the operations will be, and so
[43:27] on. But there is also the bottom-up
[43:30] approach, which is if you have existing
[43:32] data models and capabilities, then you
[43:34] should design the API based on this. So,
### chunk 66 [43:34]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

dels and capabilities, then you
[43:34] should design the API based on this. So,[43:37] this is more common when you're working
[43:39] in a company and they already have their
[43:41] data models and capabilities of their
[43:44] APIs. So, you should take that into
[43:46] account when designing the API.
[43:49] And we also have contract first
[43:50] approach, which is you define the API
[43:53] contract before implementation, meaning
[43:55] what the requests should look like and
[43:58] what the responses should look like. And
[44:00] this is more similar to top-down
[44:02] approach and this is also commonly used
[44:04] in interviews.
[44:06] When it comes to life cycle management
[44:08] of APIs, it starts with the design phase
[44:11] where you design the API, discuss the
[44:14] requirements, and the expected outcomes
### chunk 67 [44:14]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 you design the API, discuss the
[44:14] requirements, and the expected outcomes[44:16] of the API. And only after that you can
[44:19] start the development and maybe local
[44:22] testing of your API.
[44:24] After that, you usually deploy and
[44:26] monitor it, so you do some more testing,
[44:28] but now on staging or on production.
[44:31] But then it also comes the maintenance
[44:33] phase, and this is why it's important to
[44:36] develop it with keeping the simplicity
[44:38] in place, so it will be easier for you
[44:41] to maintain or for other developers to
[44:43] maintain in the future.
[44:45] And lastly, APIs also go through
[44:47] deprecation and retirement phase. So,
[44:50] some APIs eventually get deprecated
[44:52] because there might come up with a new
[44:54] version of the API that you should use,
### chunk 68 [44:54]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

e there might come up with a new
[44:54] version of the API that you should use,[44:57] or let's say you are transitioning from
[44:59] V1 to V2 API. So, that's also the
[45:02] deprecation phase of the V1 API.
[45:05] So, developing APIs is not only in the
[45:08] development phase, as you might assume.
[45:10] It's not just coding. So, the big part
[45:12] of it is designing it, and also keeping
[45:15] it maintainable, and also eventually you
[45:18] might need to retire it at the end.
[45:21] So, let's recap and see what our next
[45:23] steps are. We learned what APIs are and
[45:26] about the most dominant three type of
[45:28] API styles, which are RESTful, GraphQL,
[45:31] and gRPC.
[45:33] We've covered the four key principles
[45:35] that will guide us when creating API
[45:38] designs effectively. And you now also
### chunk 69 [45:38]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

at will guide us when creating API
[45:38] designs effectively. And you now also[45:40] understand how the design choice of your
[45:43] protocol will influence the design of
[45:45] your API, and also the whole API design
[45:48] process from start to finish.
[45:51] But we didn't discuss the limitations
[45:53] and strengths of these API protocols.
[45:56] So, that's why in the next lesson, we
[45:58] will learn all about the API protocols
[46:00] that we can use with API design and
[46:03] which one we should choose based on the
[46:05] requirements of our API. Choosing the
[46:07] wrong protocol for our API can lead to
[46:10] performance bottlenecks and also
[46:12] limitations in functionality. That's why
[46:14] we need to first understand these
[46:16] protocols which will allow us to build
[46:18] APIs that meet our specific user
### chunk 70 [46:18]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 protocols which will allow us to build
[46:18] APIs that meet our specific user[46:21] requirements for latency, throughput,
[46:23] and also interaction patterns. That's
[46:26] why in this lesson we'll cover the role
[46:28] of API protocols in the network stack,
[46:31] the two fundamental protocols which are
[46:33] HTTP and HTTPS, and also their
[46:36] relationship to APIs.
[46:38] Also, another common type of protocol
[46:40] which is WebSocket for real-time
[46:42] communication. We'll also cover advanced
[46:45] message queuing protocol which is
[46:47] commonly used for asynchronous
[46:49] communication. And lastly, we'll cover
[46:51] the gRPC which is Google's remote
[46:53] procedure call and it is also another
[46:56] common type of protocol used commonly
[46:58] within servers. Let's start by
[47:00] understanding the application protocols
### chunk 71 [47:00]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

] within servers. Let's start by
[47:00] understanding the application protocols[47:03] in network stack. Application layer
[47:05] protocols sit at the top of network
[47:08] stack building on top of protocols like
[47:10] TCP and UDP which are at the transport
[47:14] layer. These protocols at application
[47:16] layer define the message formats and
[47:19] structures, also the request response
[47:21] patterns, and management of the
[47:24] connections and error handling.
[47:26] Now, below that we have many other
[47:28] layers like the network layer or data
[47:31] link layer or even physical layers, but
[47:33] when building APIs, we are mostly
[47:35] concerned with the API layer protocols
[47:38] which are HTTP, HTTPS, WebSockets, and
[47:41] so on. The most common type of protocol
[47:44] and also the foundation of web APIs is
### chunk 72 [47:44]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 The most common type of protocol
[47:44] and also the foundation of web APIs is[47:47] HTTP which stands for Hypertext Transfer
[47:50] Protocol. This is the typical
[47:52] interaction between client and server
[47:54] when they are interacting over HTTP. As
[47:56] you can see, client always sends a
[47:58] request and they define the method which
[48:00] can be get, post, or other methods and
[48:03] they define the resource URL which can
[48:06] be at {slash} API {slash} products.
[48:08] Let's say they are requesting data for
[48:10] this specific ID of the product and they
[48:13] also define the version of the HTTP
[48:15] protocol that they are using. They also
[48:18] define the host which is the domain of
[48:20] your server where the information is
[48:22] accessed and usually they also
[48:25] authenticate before accessing any
### chunk 73 [48:22]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

[48:22] accessed and usually they also
[48:25] authenticate before accessing any[48:27] resources. So, it can be either a bearer
[48:29] token or a basic authentication, OAuth,
[48:32] and so on. So, once the request is
[48:34] authenticated in the server, it receives
[48:37] the response which is in similar format
[48:39] and it's in HTTP response. So, you get
[48:42] the HTTP version which is again the same
[48:45] as you requested with and the status
[48:47] code which can be 200 if it was
[48:49] successful or it can be 400 if the
[48:51] client was error or 500 if the error
[48:55] happened in server and so on. You
[48:57] receive the content type which can be
[48:59] usually application JSON, but it can
[49:01] also be a static web page or something
[49:04] else. And there are many other headers
[49:06] that you can control like controlling
### chunk 74 [49:06]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

. And there are many other headers
[49:06] that you can control like controlling[49:08] cache, you can use the cache control
[49:10] header or some other properties, but
[49:13] these are the main things that you would
[49:14] notice in HTTP request response cycles.
[49:18] Now, when it comes to methods, you have
[49:19] get for retrieving data, post for
[49:22] creating data in the server, put or
[49:25] patch for updating data partially or
[49:27] fully, and delete for removing data from
[49:30] the server. And when it comes to status
[49:33] codes which are received by the server,
[49:35] so you have 200 series which are
[49:37] successful cases. You have 300 for
[49:40] redirection. 400 means that client made
[49:43] an error in the request, so this is an
[49:45] issue from client side or 500 which
[49:47] means that server made an error or like
### chunk 75 [49:47]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ue from client side or 500 which
[49:47] means that server made an error or like[49:50] some error happened in the server which
[49:52] means that this is the issue in this
[49:53] server. And And these are the common
[49:56] headers like content type, which is
[49:57] defined by the server usually, but also
[50:00] from the client, authorization for
[50:02] making a request and authorizing to the
[50:05] server, accept headers, cache control,
[50:07] user agent, and there are more headers,
[50:09] but these are the common ones. Then we
[50:11] also have HTTPS, which is basically the
[50:14] same HTTP protocol, but with some sort
[50:17] of TLS or SSL encryption, which means
[50:20] that our data is now protected in
[50:22] transit when we are making requests. So
[50:25] it adds a security layer through these
[50:27] TLS or SSL certificates and encryption,
### chunk 76 [50:27]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

s a security layer through these
[50:27] TLS or SSL certificates and encryption,[50:30] so and it protects data in the transit.
[50:33] And benefits of HTTPS is obviously your
[50:35] data is encrypted in the transit, it
[50:38] comes with data integrity, and you also
[50:40] authenticate users before providing any
[50:42] data, and it also adds SEO benefits, and
[50:45] you have many risks when you are using
[50:47] HTTP only without any encryption. So the
[50:50] golden standard is to always use HTTPS
[50:53] in servers.
[50:55] The next type of protocols are web
[50:57] sockets. While we have HTTP, which is
[50:59] very good at request-response patterns,
[51:02] sometimes HTTP has limitations. For
[51:05] example, let's say you're polling some
[51:06] data. Let's say this is a user chat, so
[51:09] you have the client and server. On the
### chunk 77 [51:09]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

Let's say this is a user chat, so
[51:09] you have the client and server. On the[51:11] client side, you have the user chat, and
[51:13] on the server, you have the messages
[51:15] between two users.
[51:16] When one of the users messages the
[51:18] other, it sends a request to the server
[51:21] to notify that a message has been sent,
[51:24] and it receives a response from the
[51:25] server, maybe the messages from the
[51:28] other users, if there are any. And then
[51:30] next time, if you need to know if you
[51:32] have new messages, you need to make
[51:34] again another request to the server, and
[51:37] maybe you don't have any new messages,
[51:39] so you will receive an empty response
[51:41] with no new data. So this was basically
[51:43] a unnecessary request-response cycle,
[51:46] and you might request from some other
### chunk 78 [51:46]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

nnecessary request-response cycle,
[51:46] and you might request from some other[51:48] time, let's say from 1 minute and
[51:50] receive a response. Now you have some
[51:52] messages, but it can be also empty
[51:54] again. So, this way is not ideal for
[51:58] real-time communication. As you can see,
[52:00] you get increased latency, you waste
[52:02] some bandwidth with making requests that
[52:04] are empty, and you also use the server
[52:07] resources without the need of making
[52:09] requests to the server. And for such
[52:12] cases, we have WebSockets, which solve
[52:14] this issue. So, in WebSocket, you have
[52:17] usually a handshake that is happening
[52:19] within the first request and now you
[52:21] have both like two-side communication
[52:23] between client and the server, which
[52:25] means that once the handshake has been
### chunk 79 [52:25]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ween client and the server, which
[52:25] means that once the handshake has been[52:27] made, the server can independently
[52:30] decide to push data to the client. Let's
[52:32] say now you have two new messages on the
[52:35] server. So, server can decide to send
[52:37] these messages to the client without
[52:39] even client requesting for it. But,
[52:42] client can still request data. So, if
[52:45] client needs some external data or more
[52:47] data from the server, it can still make
[52:49] requests, but server is now also able to
[52:52] independently push data to the client.
[52:55] So, this is what unlocks the real-time
[52:57] data with minimal latency. As soon as
[53:00] you have some new data in the server, it
[53:02] pushes the new data to the client and it
[53:05] also reduces the bandwidth usage by
[53:07] allowing bidirectional communication. In
### chunk 80 [53:07]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 reduces the bandwidth usage by
[53:07] allowing bidirectional communication. In[53:10] client-server model with HTTP, you would
[53:12] make, let's say, new requests per 5
[53:15] seconds or 10 seconds to see if there
[53:17] are any new data in the server. But, in
[53:20] this scenario, you don't make any more
[53:22] requests other than the first one. And
[53:24] now, whenever there are new data, server
[53:26] will push it. And whenever there are no
[53:29] data to be requested, then you don't
[53:31] need to make unnecessary requests to the
[53:33] server.
[53:34] The next very common type of protocol is
[53:37] Advanced Message Queuing Protocol, which
[53:39] is an enterprise messaging protocol used
[53:42] for message queuing and guaranteeing
[53:44] delivery. In this setup, you usually
[53:47] have the producer, which can be either a
### chunk 81 [53:47]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ery. In this setup, you usually
[53:47] have the producer, which can be either a[53:49] web service or payment system or
[53:52] something like that. And on the other
[53:54] side, you have the consumer, which can
[53:56] be the processor of the payments or
[53:58] notification systems and stuff like
[54:01] that.
[54:01] So, a producer publishes messages to the
[54:04] message broker, and here is where you
[54:06] have the advanced message queuing
[54:08] protocol. You have queues in the middle.
[54:11] Let's say one of these queues is for
[54:13] order processing. So, whenever a new
[54:15] order has been placed, producer
[54:17] publishes a message to this queue. And
[54:19] then whenever this consumer is free, it
[54:22] can pull messages from this queue and
[54:24] start updating the inventory and data in
[54:27] the database. This allows the consumer
### chunk 82 [54:27]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

pdating the inventory and data in
[54:27] the database. This allows the consumer[54:29] to only pull data from here whenever it
[54:32] has capacity. And whenever this consumer
[54:35] is busy with some other tasks, it leaves
[54:37] the message in the queue and then later
[54:40] on, whenever it has some free capacity,
[54:42] it will pull the message and start
[54:44] updating the data. And when it comes to
[54:46] exchange types, you have direct
[54:48] one-on-one exchange or fan out or
[54:51] topic-based communication. And we will
[54:54] explore these more when we come to the
[54:56] message queuing section.
[54:58] The other common type of protocol is
[55:00] gRPC, which works with protocol buffers.
[55:04] This is a high-performance RPC framework
[55:06] invented by Google, and it uses HTTP 2
[55:09] for transport, meaning the second
### chunk 83 [55:09]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

invented by Google, and it uses HTTP 2
[55:09] for transport, meaning the second[55:11] version of the HTTP. This means that
[55:14] clients should support HTTP 2, otherwise
[55:17] this can't be used between client and
[55:19] server. But that's why this is most
[55:22] commonly used between servers. So,
[55:24] usually the client is another server,
[55:26] and we have some other microservices
[55:28] communicating with each other with this
[55:30] gRPC framework. It mainly uses protocol
[55:34] buffers, and it also comes with built-in
[55:36] streaming capacities because it uses
[55:38] HTTP 2. So, these are the most common
[55:41] types of API protocols. There are many
[55:44] more, but usually in 90% of cases you
[55:47] would see only these protocols. And when
[55:49] choosing the right one, you should
[55:51] mainly consider the interaction
### chunk 84 [55:51]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

5:49] choosing the right one, you should
[55:51] mainly consider the interaction[55:53] patterns. Usually by default you go with
[55:55] HTTP if it's just a request-response
[55:57] cycle, but if you're building something
[55:59] like real-time chat or some real-time
[56:02] communication, then you would need to go
[56:03] with WebSockets. The choice also depends
[56:06] from the performance requirements. So,
[56:08] if you have multiple servers,
[56:10] microservices communicating with each
[56:12] other, and there is an opportunity to
[56:14] use gRPC, for example, then you can go
[56:17] with it to increase the performance and
[56:19] speed of the communication. But it also
[56:22] comes down to client compatibility. For
[56:24] example, most browsers don't support the
[56:26] latest version of the HTTP. That's why
[56:29] gRPC isn't that very common for
### chunk 85 [56:29]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

] latest version of the HTTP. That's why
[56:29] gRPC isn't that very common for[56:31] browser-server communication.
[56:34] It also comes down to the payload size,
[56:36] meaning the volume of the data and
[56:38] encoding, security needs based on the
[56:41] authentication, encryption, and so on,
[56:43] and also the developer experience, so
[56:45] the tooling and documentation. And it
[56:48] also comes down to the developer
[56:50] experience because you're mostly going
[56:51] to work with this API, and it needs to
[56:54] have good documentation and tooling for
[56:56] you to fully work with this type of API
[56:59] protocol.
[57:00] So, to recap, we have explored the role
[57:02] of application protocols in network
[57:05] the HTTP and HTTPS, which are the most
[57:08] fundamental types of protocols,
[57:11] WebSockets for real-time communication,
### chunk 86 [57:11]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 fundamental types of protocols,
[57:11] WebSockets for real-time communication,[57:13] AMQP, which stands for Advanced Message
[57:16] Queuing Protocol, which allows us to
[57:18] have asynchronous communication and
[57:20] adding message queues between the
[57:22] consumer and producer, and also gRPC,
[57:25] which stands for Google Remote Procedure
[57:27] Call, and the main advantage of this is
[57:30] is it's high-performance RPC framework,
[57:32] which uses HTTP/2 for transport.
[57:35] So, we discussed the application layer,
[57:37] which includes these protocols that we
[57:39] usually use for building APIs, but we
[57:42] don't know yet about this transport
[57:44] layer, which includes the TCP and UDP.
[57:47] So, in the next lesson, we are going to
[57:49] discuss this layer and understand which
[57:52] of these transport layers, whether TCP
### chunk 87 [57:52]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

s this layer and understand which
[57:52] of these transport layers, whether TCP[57:54] or UDP, are the best choice depending on
[57:57] the API that we are building. Most
[58:00] developers work APIs, but never think
[58:02] about what's actually delivering those
[58:04] packets. Like, how does it happen that
[58:07] the request is being made from client to
[58:09] server, and how does this request go
[58:12] through the internet? That's where the
[58:14] second layer comes in in the OSI model,
[58:17] which is the transport layer that has
[58:19] the TCP and UDP inside of it.
[58:22] These are both transport layer
[58:24] protocols, meaning they handle how data
[58:26] moves from one machine to another over
[58:29] the network. But, both are doing it very
[58:32] differently.
[58:33] In this lesson, we'll learn about these
### chunk 88 [58:32]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ing it very
[58:32] differently.
[58:33] In this lesson, we'll learn about these[58:35] transport layer protocols. We'll start
[58:37] with TCP, which is the reliable but
[58:40] slower version. Then, we'll learn about
[58:42] the UDP, which is In short, it's faster
[58:44] and unreliable version of TCP. And,
[58:48] we'll compare both of them and decide
[58:50] which one we need to choose based on the
[58:52] API requirements.
[58:54] Let's start with TCP, which stands for
[58:56] Transmission Control Protocol. Think of
[58:59] it like sending a packet with a receipt,
[59:01] tracking, and also signature that is
[59:04] required. So, when you send some packets
[59:06] over the internet, you usually don't
[59:08] send all of it at once. Sometimes, the
[59:11] data is larger. Let's say it's divided
[59:13] in three chunks, so you need to send
### chunk 89 [59:13]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

a is larger. Let's say it's divided
[59:13] in three chunks, so you need to send[59:15] them separately. The first chunk, the
[59:17] second chunk, and also the third chunk.
[59:20] So, in this case, TCP guarantees
[59:22] delivery of all of these three chunks.
[59:25] If one of these packets is lost or
[59:27] arrives out of order, TCP will resend or
[59:31] reorder it.
[59:32] It's also connection-based, which means
[59:34] that before sending any data, it
[59:36] performs a three-way handshake, which is
[59:39] establishing the connection between
[59:41] client and server.
[59:43] It also orders these packets. Let's say
[59:46] the client receives the first packet
[59:48] first, then the third packet, then the
[59:50] second packet. It makes sure that it's
[59:52] reordered to first, second, and third.
[59:55] This, of course, adds overhead, but it
### chunk 90 [59:55]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ered to first, second, and third.
[59:55] This, of course, adds overhead, but it[59:58] ensures that it's accurate and reliable.
[01:00:01] That's why APIs that involve payments,
[01:00:03] authentication, or user data always use
[01:00:06] TCP. On the other hand, we have UDP,
[01:00:08] which stands for User Datagram Protocol.
[01:00:11] It's fast and efficient, but the
[01:00:14] downside of this is that it doesn't
[01:00:15] guarantee that all of the packets will
[01:00:18] arrive. For example, if you're sending
[01:00:20] four packets from the server to the
[01:00:22] client, one of these packets might be
[01:00:24] lost, and it won't be pushed to the
[01:00:26] client, and UDP won't make sure that
[01:00:29] this eventually gets delivered. So,
[01:00:31] there is no delivery guarantee. There is
[01:00:34] also no handshake or connection or any
### chunk 91 [01:00:34]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

o delivery guarantee. There is
[01:00:34] also no handshake or connection or any[01:00:37] sort of tracking. But because of these
[01:00:39] tradeoffs, it is faster transmission,
[01:00:42] and it comes with less overhead as it
[01:00:44] doesn't need to make sure that all of
[01:00:46] the packets are delivered or in the
[01:00:49] correct order. For example, in video
[01:00:51] calls, UDP can be the best protocol
[01:00:54] because if some information was cut in
[01:00:57] the middle, or let's say you're in a
[01:00:58] call with someone and their internet
[01:01:00] connection lags, you don't need to
[01:01:02] receive that old connection or the old
[01:01:05] data on what they said because you are
[01:01:07] in the call right now. So, UDP is the
[01:01:09] go-to for video calls, online games, or
[01:01:12] live streams because if one of these
### chunk 92 [01:01:12]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

or video calls, online games, or
[01:01:12] live streams because if one of these[01:01:14] packets drops, it's still fine, and you
[01:01:17] don't need to go back and resend this
[01:01:19] packet. You can just move on and send
[01:01:21] the next packets.
[01:01:23] This is what the three-step handshake
[01:01:25] looks like in TCP. As you can see, the
[01:01:28] first step is that client sends a
[01:01:30] request to the server. In the second
[01:01:32] step, server syncs and acknowledges the
[01:01:34] request. And in the first step, the
[01:01:37] client acknowledges the server. And this
[01:01:39] is where the connection is established
[01:01:41] between the client and server. And now
[01:01:44] they can start sending data back and
[01:01:46] forth on top of this TCP protocol.
[01:01:49] So, in short, TCP is the safer and
### chunk 93 [01:01:49]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

forth on top of this TCP protocol.
[01:01:49] So, in short, TCP is the safer and[01:01:52] reliable version of UDP, but it is
[01:01:54] slower. And on the other hand, UDP is
[01:01:57] faster and lightweight, but it is risky.
[01:02:00] For example, if one of the packets in
[01:02:02] between the source and destination is
[01:02:04] lost, it doesn't resend it, so there is
[01:02:07] no guaranteed delivery. But on the other
[01:02:09] hand, if in TCP one of the packets is
[01:02:11] lost, after some timeout, it still
[01:02:14] resends the third packets. And this way,
[01:02:17] it guarantees that all data will be
[01:02:19] delivered compared to UDP, where some
[01:02:21] data might be lost, but it will still
[01:02:23] keep going. And when choosing between
[01:02:25] those two, these are the main things
[01:02:27] that you need to look for. If you need
### chunk 94 [01:02:27]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

two, these are the main things
[01:02:27] that you need to look for. If you need[01:02:29] the connection to be safe and reliable,
[01:02:32] then you need to go with TCP. Or if you
[01:02:34] need it to be fast, lightweight, but
[01:02:36] some data loss might be acceptable, then
[01:02:39] you will need to go with UDP. For
[01:02:41] example, it is best for using TCP in
[01:02:44] bankings, emails, payments, and so on.
[01:02:47] And on the other hand, UDP is mostly
[01:02:49] used in video streaming, streaming,
[01:02:51] gaming, and so on.
[01:02:53] These are the main things that you need
[01:02:55] to know about the application and
[01:02:57] transport layers. And these are the only
[01:02:59] layers that will need to be used to
[01:03:01] building APIs. And in the next lesson,
[01:03:04] we will learn about RESTful APIs and how
### chunk 95 [01:03:04]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

PIs. And in the next lesson,
[01:03:04] we will learn about RESTful APIs and how[01:03:07] we usually design APIs in RESTful
[01:03:09] format. RESTful APIs let different parts
[01:03:13] of a system talk to each other using the
[01:03:15] standard HTTP methods. they are the most
[01:03:18] common way developers build and consume
[01:03:21] APIs today. And in this video, you'll
[01:03:23] learn how to design clean REST APIs by
[01:03:26] following the proven best practices so
[01:03:28] that you avoid creating messy and
[01:03:30] inconsistent patterns that make the APIs
[01:03:33] hard to use and maintain. We'll start by
[01:03:36] learning about the architectural
[01:03:38] principles and constraints of RESTful
[01:03:41] APIs, about the resource modeling and
[01:03:44] URL design, also the status codes and
[01:03:47] the error handling as well as filtering,
### chunk 96 [01:03:47]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

n, also the status codes and
[01:03:47] the error handling as well as filtering,[01:03:50] sorting, and so on.
[01:03:52] And we'll learn the best practices when
[01:03:54] using and developing RESTful APIs.
[01:03:57] Let's start from the resource modeling.
[01:03:59] Resources are the core concepts in REST.
[01:04:02] Let's say you have the business domain
[01:04:04] which consists of the products, orders,
[01:04:07] and reviews. When modeling these to a
[01:04:09] RESTful API, you usually convert these
[01:04:12] into nouns and not verbs, meaning that
[01:04:15] the product becomes products, order
[01:04:17] becomes orders, and same for the
[01:04:19] reviews. These can be collections or
[01:04:22] individual items. For example, this
[01:04:25] first request, which is to {slash} API
[01:04:27] {slash} products, will return you the
### chunk 97 [01:04:27]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

equest, which is to {slash} API
[01:04:27] {slash} products, will return you the[01:04:29] collection of products, not a single
[01:04:31] product. But on the other hand, you
[01:04:33] could have {slash} products and {slash}
[01:04:35] specific ID of a product, which will
[01:04:38] return you the individual item. And
[01:04:40] notice that we are using {slash}
[01:04:42] products when retrieving the collection
[01:04:45] of products, and we are not using
[01:04:47] something like get products, which will
[01:04:49] be not a best practice in RESTful APIs.
[01:04:53] As I mentioned, we are using nouns here
[01:04:55] and not verbs. So, to fetch orders, for
[01:04:58] example, you don't define the URL as get
[01:05:01] orders. You just define it as {slash}
[01:05:03] orders, and depending on the method that
[01:05:06] we'll use, let's say it's a get method,
### chunk 98 [01:05:06]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 depending on the method that
[01:05:06] we'll use, let's say it's a get method,[01:05:07] then you will retrieve the orders. If
[01:05:09] it's a post method, then you will create
[01:05:11] an order, and so on. So, all the
[01:05:14] resources should be clearly identifiable
[01:05:17] through the URLs. For instance, this is
[01:05:19] an example of getting a collection. This
[01:05:22] is an example of getting a specific
[01:05:24] item. And also, nested resources should
[01:05:27] be clearly defined. For example, if you
[01:05:30] want to retrieve reviews for some
[01:05:32] specific product, then we would assume
[01:05:34] that if you make a request to {slash}
[01:05:36] products {slash} ID of that product, and
[01:05:39] then {slash} reviews, you would get the
[01:05:41] reviews for that specific product. But,
[01:05:44] in real-world APIs, you rarely want to
### chunk 99 [01:05:44]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

or that specific product. But,
[01:05:44] in real-world APIs, you rarely want to[01:05:46] return all the results at once. That's
[01:05:49] why we usually incorporate filtering,
[01:05:51] sorting, and pagination in APIs. So,
[01:05:54] let's start from the filtering. For
[01:05:56] example, if you make a request to get
[01:05:58] all the products, you usually add some
[01:06:00] query parameter, which in this case you
[01:06:03] can see it's category. So, you're first
[01:06:05] of all filtering them by category. And
[01:06:07] then also, with the end sign, you add
[01:06:10] that they should be in stock. So, the in
[01:06:12] stock should be true. And this way, you
[01:06:15] are only returning the items that you're
[01:06:17] going to display on the UI. And you're
[01:06:20] not making some requests that will waste
### chunk 100 [01:06:20]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

isplay on the UI. And you're
[01:06:20] not making some requests that will waste[01:06:22] the bandwidth of this API, and also, it
[01:06:25] will be a huge response for you in the
[01:06:27] front-end side. Next, we also have
[01:06:29] sorting. In this case, again, it's
[01:06:31] controlled through the query parameters.
[01:06:34] And query parameters are anything that
[01:06:36] start after the question mark in the
[01:06:38] URL. So, in this case, you usually pass
[01:06:40] the sort attribute. And this can be, for
[01:06:43] example, ascending by price, or
[01:06:46] ascending by reviews, or it can be also
[01:06:49] the descending order. So, based on this,
[01:06:51] you will get the response from the API
[01:06:54] in a sorted order. Because if you, for
[01:06:56] example, have 1,000 items in the
[01:06:59] back-end, in the database, you don't
### chunk 101 [01:06:59]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

example, have 1,000 items in the
[01:06:59] back-end, in the database, you don't[01:07:01] want to retrieve all of these in
[01:07:03] unsorted order to the front-end.
[01:07:06] Because, let's say the front end now
[01:07:07] needs to sort them by the price
[01:07:10] ascending. This means that it needs to
[01:07:12] make request to get all of the products,
[01:07:14] which are these thousand items that you
[01:07:17] have in the database. So, that will be
[01:07:19] very inefficient. That's why we do the
[01:07:21] sorting in the back end instead. So,
[01:07:23] your back end should support sorting
[01:07:25] functionality. This way the front end
[01:07:28] can just make a request to your back end
[01:07:30] and pass this sort query parameter and
[01:07:33] then that way it will get the sorted
[01:07:36] products to be displayed on the screen.
### chunk 102 [01:07:36]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

at way it will get the sorted
[01:07:36] products to be displayed on the screen.[01:07:39] And next we also have pagination. Again,
[01:07:41] with a query parameter, you usually pass
[01:07:43] the page which you want to retrieve and
[01:07:45] also the limit because if you don't pass
[01:07:48] the limit, then again it will give you
[01:07:50] all of the products starting from the
[01:07:52] page two till the end, which can be a
[01:07:55] lot of items. So, you also pass some
[01:07:57] sort of limit and that limit is whatever
[01:08:00] you're going to display on the front
[01:08:01] end. And then based on that, you will
[01:08:03] get the response and here let's say you
[01:08:05] fetched 10 items. So, you're going to
[01:08:08] display those 10 on the UI and then once
[01:08:10] they click on the next page, you will
### chunk 103 [01:08:10]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

hose 10 on the UI and then once
[01:08:10] they click on the next page, you will[01:08:12] make another request to the page three
[01:08:15] this time and you will get the next
[01:08:17] items from the server.
[01:08:19] Now, usually we use page for pagination,
[01:08:21] but there is another common attribute
[01:08:23] that is offset. So, some APIs use offset
[01:08:27] instead of the page and they use this in
[01:08:29] combination with limit, which basically
[01:08:31] means if you have thousand items. So,
[01:08:34] offset will tell the API from where to
[01:08:37] start counting these thousand items and
[01:08:40] then limit is the same as you have it
[01:08:42] here. So, it's basically limiting the
[01:08:44] number of items that you are getting
[01:08:46] from this offset to retrieve to the
[01:08:48] front end.
### chunk 104 [01:08:46]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

are getting
[01:08:46] from this offset to retrieve to the
[01:08:48] front end.[01:08:49] And the last option, you can also have
[01:08:51] this cursor based. So, instead of page
[01:08:54] and limit, you would pass a cursor,
[01:08:56] which will be the hash of the page you
[01:08:58] want to retrieve.
[01:08:59] So, this approach of adding filtering,
[01:09:02] sorting, and pagination comes with
[01:09:04] benefits. So, first of all, it saves the
[01:09:06] bandwidth of your server. It also
[01:09:08] improves the performance both in the
[01:09:10] server side and on the front end side.
[01:09:12] And it also gives the front end more
[01:09:14] flexibility because now you can fetch
[01:09:17] only the things that you need and not
[01:09:19] some unnecessary data from the database.
[01:09:22] Now, let's come to the HTTP methods that
### chunk 105 [01:09:22]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

sary data from the database.
[01:09:22] Now, let's come to the HTTP methods that[01:09:24] REST APIs use because they rely on HTTP
[01:09:28] protocol and hence they are using the
[01:09:30] HTTP methods, especially for CRUD
[01:09:33] operations. So, these are the most
[01:09:35] common types of CRUD operations you
[01:09:38] would see in REST APIs. First of all, we
[01:09:40] have the GET method, which is used for
[01:09:43] reading data from the API. So, this is
[01:09:45] for retrieving resources, as you saw,
[01:09:48] like retrieving the products, retrieving
[01:09:50] the reviews, and so on. And the URL
[01:09:53] usually looks like this. You make a GET
[01:09:55] request to the /api/version
[01:09:58] of the API/the resource name. And these
[01:10:01] type of requests are both safe and
[01:10:04] idempotent, which basically means if you
### chunk 106 [01:10:04]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

f requests are both safe and
[01:10:04] idempotent, which basically means if you[01:10:07] make a request to /products two or three
[01:10:10] times, you expect to receive the exact
[01:10:12] same output every time unless some new
[01:10:15] products obviously have been added to
[01:10:17] the database. Next, we have the POST
[01:10:20] method. This is usually when you're
[01:10:21] creating a resource in your server. The
[01:10:24] common example is again, you will make
[01:10:26] the request to exact same endpoint as
[01:10:29] you have it for the GET to create a
[01:10:31] collection. But in this case, instead of
[01:10:33] GET, you are using POST method. And this
[01:10:36] tells the API that you need to create a
[01:10:39] resource in the products and not
[01:10:41] retrieve them.
[01:10:42] These type of requests change the state
### chunk 107 [01:10:41]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

not
[01:10:41] retrieve them.
[01:10:42] These type of requests change the state[01:10:44] of the server. They are adding a new
[01:10:46] item and also they are not idempotent,
[01:10:49] which means that they are creating a
[01:10:51] resource. So, the first time you create
[01:10:53] a resource, you will get the ID of the
[01:10:55] first item that you created. The second
[01:10:58] time you created you will get the ID of
[01:11:00] the second one and so on. Next we have
[01:11:03] the put and patch methods which are very
[01:11:06] similar but they are updating resources
[01:11:08] in your API. But they do it a bit
[01:11:11] differently. The put method replaces the
[01:11:14] whole resource whereas the patch method
[01:11:16] partially updates the resource in your
[01:11:19] API. Now you can see that the request
### chunk 108 [01:11:19]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ly updates the resource in your
[01:11:19] API. Now you can see that the request[01:11:21] URL is exactly the same in both of their
[01:11:24] cases so it's tool {slash} products
[01:11:26] {slash} ID of a product you want to
[01:11:28] modify. Just in case of the put request
[01:11:31] it will take this whole product with the
[01:11:33] ID of 123 and it will basically replace
[01:11:37] it with the new one that is coming from
[01:11:39] the front end. Whereas in case of the
[01:11:41] patch it will again take this item from
[01:11:43] the database with ID 123 but it will
[01:11:46] update it partially. Let's say you just
[01:11:49] updated the title from the front end and
[01:11:52] you made the request with patch method.
[01:11:54] So this will only update the title of
[01:11:57] this product and it will leave the other
[01:11:59] parts other properties unchanged.
### chunk 109 [01:11:59]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

product and it will leave the other
[01:11:59] parts other properties unchanged.[01:12:02] And the last crowd operation is delete
[01:12:04] and we use delete method in this case
[01:12:07] and obviously as the name tells it
[01:12:09] deletes the resource from the database.
[01:12:11] So again the URL is exactly the same as
[01:12:14] you have for modifying items. It's tool
[01:12:17] {slash} products {slash} ID of the
[01:12:19] resource and in this case you are not
[01:12:21] passing anything in the request body so
[01:12:23] you are just making a delete request to
[01:12:26] this item and you are removing this from
[01:12:28] the database. And each of these
[01:12:30] operations return you different status
[01:12:33] codes depending on how the request went
[01:12:36] whether it was successful or not. For
[01:12:38] that we have status codes and error
### chunk 110 [01:12:38]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

her it was successful or not. For
[01:12:38] that we have status codes and error[01:12:40] handling in restful APIs.
[01:12:42] So you should use the appropriate status
[01:12:45] codes when working with rest APIs. For
[01:12:47] example the 200 series are for
[01:12:50] successful requests. For example 200 is
[01:12:53] okay, 201 is resource has been created,
[01:12:56] 204 is there is no content here.
[01:12:59] Let's say you made a request, the
[01:13:01] previous request we were talking about
[01:13:03] to {slash} products {slash} some ID of a
[01:13:05] product, and you successfully retrieved
[01:13:08] this item. This means that you also need
[01:13:10] to set the status code to 200 because
[01:13:13] the request has been successful. In the
[01:13:16] other case where you're creating a
[01:13:17] product and you're making a post request
### chunk 111 [01:13:17]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

case where you're creating a
[01:13:17] product and you're making a post request[01:13:19] to {slash} products, this time you
[01:13:21] shouldn't respond with the same 200 code
[01:13:24] because 200 generally means that the
[01:13:26] status was okay. But in 201 case, it
[01:13:30] means that the resource has been
[01:13:31] created. And in this case, since you're
[01:13:33] creating a new product, you should
[01:13:35] obviously respond with the 201 status
[01:13:38] code, meaning resource has been created.
[01:13:40] You also have 300 series, which are for
[01:13:42] redirection. Let's say you make a
[01:13:44] request to a URL, and now this URL has
[01:13:47] been moved to somewhere else. So, it
[01:13:49] will respond with a 300 series, and it
[01:13:52] will redirect you to the new URL. In 400
[01:13:56] series, we have the client errors. So,
### chunk 112 [01:13:56]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ect you to the new URL. In 400
[01:13:56] series, we have the client errors. So,[01:13:58] this is whenever your front end made a
[01:14:00] bad request or the user made a bad
[01:14:02] request. For example, 400 is a generic
[01:14:05] bad request. In 401, we have
[01:14:08] unauthorized requests, meaning the user
[01:14:10] is not authenticated to make this
[01:14:12] request. For 404, we have not found. So,
[01:14:16] generally when you visit some URL or you
[01:14:18] make a request for some specific
[01:14:20] resource that doesn't exist, you would
[01:14:22] get this 404 status code.
[01:14:25] So, for 400 case, let's say you made a
[01:14:27] request with invalid parameters or some
[01:14:30] wrong JSON format. In this case, you
[01:14:32] would get a generic 400 bad request. But
[01:14:36] if a user makes a request to to get some
### chunk 113 [01:14:36]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

generic 400 bad request. But
[01:14:36] if a user makes a request to to get some[01:14:38] product, which is let's say the product
[01:14:41] with this ID, and it doesn't exist in
[01:14:43] the database after querying it, then you
[01:14:46] should respond with the 404 status code,
[01:14:49] meaning that the resource has not been
[01:14:51] found.
[01:14:52] And lastly, we have 500 series. These
[01:14:54] are things when error happens in your
[01:14:56] server, so you don't know the exact
[01:14:59] reason, and it's also not a client
[01:15:01] error, meaning client requested
[01:15:03] everything properly. And in this case,
[01:15:05] we throw unexpected server-side errors.
[01:15:08] You generally respond with a server
[01:15:10] error message, and you return the 500
[01:15:13] status code along with it.
[01:15:15] When it comes to best practices of
### chunk 114 [01:15:15]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

:15:13] status code along with it.
[01:15:15] When it comes to best practices of[01:15:17] RESTful APIs, first of all, notice that
[01:15:20] we are using plural nouns for all of the
[01:15:22] resources. So, instead of {slash}
[01:15:24] product, we are using {slash} products
[01:15:27] for retrieving the products collection.
[01:15:30] So, you should always use the plural in
[01:15:32] this case. Also, in the CRUD operations,
[01:15:35] we use the proper HTTP methods. For
[01:15:37] example, when making a request to delete
[01:15:40] users, we expect to make a request to
[01:15:42] users {slash} ID of a user, and not some
[01:15:45] post request to {slash} users {slash}
[01:15:48] ID. So, first of all, the HTTP methods
[01:15:50] needs to be properly set up, and also
[01:15:53] the URL. We don't expect some random
[01:15:56] things like {slash} delete to delete a
### chunk 115 [01:15:56]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

L. We don't expect some random
[01:15:56] things like {slash} delete to delete a[01:15:58] resource from the database.
[01:16:00] As you saw, we also support filtering,
[01:16:02] sorting, and pagination in good REST
[01:16:05] APIs. Not only pagination. For example,
[01:16:08] in this case, we only have the page
[01:16:10] three, but we cannot limit the amount of
[01:16:13] products that we want to retrieve.
[01:16:15] Whereas in this case, we can fully
[01:16:16] control what we want to get from the
[01:16:18] API. We want to get the items from page
[01:16:21] three. We want this number of limit to
[01:16:24] be applied on the products. And we also
[01:16:26] want to apply some sort, like sorting,
[01:16:28] to sort the price or sort by ratings,
[01:16:31] and so on. And also, versionings in the
[01:16:35] RESTful APIs. As you noticed in all of
### chunk 116 [01:16:35]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

. And also, versionings in the
[01:16:35] RESTful APIs. As you noticed in all of[01:16:37] these requests, they all come with a
[01:16:39] prefix, which is {slash} API, and then
[01:16:42] {slash} the ID of the API, which is
[01:16:44] either V1, V2, V3, and so on. Let's
[01:16:48] let's say in the future you migrate your
[01:16:51] API and you start using bunch of new
[01:16:53] features, but you also break something
[01:16:55] in the previous version one, then if you
[01:16:58] use the versioning, you won't break it
[01:16:59] on the front end because they can use
[01:17:02] the old version of your API and still
[01:17:04] use the old features and functionalities
[01:17:07] while you continue to develop the new
[01:17:09] version, let's say version three, and
[01:17:10] you support new features here and you
[01:17:12] might have broken something here, but
### chunk 117 [01:17:12]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

pport new features here and you
[01:17:12] might have broken something here, but[01:17:15] they are still using the old API, so
[01:17:17] this doesn't impact the end users.
[01:17:20] So, to recap, we learned about the REST
[01:17:22] architectural principles and
[01:17:24] constraints, also about the resource
[01:17:27] modeling and URL design, and how we
[01:17:29] model the business domain into the
[01:17:32] RESTful API domain, also the status
[01:17:35] codes, error handling, and the proper
[01:17:37] methods to be used with the basic CRUD
[01:17:40] operations.
[01:17:41] And lastly, we covered the best
[01:17:43] practices for RESTful APIs that you
[01:17:45] should use to keep your APIs consistent
[01:17:48] and also predictable for other
[01:17:51] developers who are using it. Traditional
[01:17:53] RESTful APIs often return too much or
### chunk 118 [01:17:53]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

s who are using it. Traditional
[01:17:53] RESTful APIs often return too much or[01:17:56] too little data, which requires us to do
[01:17:59] multiple requests for a single view to
[01:18:01] get all the data that we need. GraphQL
[01:18:03] solves this issue by giving clients
[01:18:05] exactly what they requested for, but
[01:18:08] designing GraphQL APIs is different from
[01:18:10] designing RESTful APIs. That's why in
[01:18:12] this video we'll cover the core concepts
[01:18:14] of GraphQL and why it exists, the schema
[01:18:18] design and type system of GraphQL,
[01:18:20] queries and mutations, error handling,
[01:18:23] and also best practices for designing
[01:18:25] GraphQL APIs. Let's start by
[01:18:28] understanding why GraphQL exists in the
[01:18:30] first place. It was created by Facebook
[01:18:32] to solve a very specific pain, which is
### chunk 119 [01:18:32]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

e. It was created by Facebook
[01:18:32] to solve a very specific pain, which is[01:18:35] clients needing to make multiple API
[01:18:37] calls and still not getting the exact
[01:18:39] data that they needed. For example, if
[01:18:41] we imagine we have the Facebook APIs
[01:18:44] like user API, post API, comments, and
[01:18:47] likes for the Facebook page. Most of the
[01:18:50] times client can make requests to all of
[01:18:52] these APIs separately and still not get
[01:18:55] all the data that it needs, which will
[01:18:57] require it to do multiple requests to
[01:18:59] the same API. This, of course, adds up
[01:19:02] to the overall latency of the page
[01:19:05] because page is still not loaded until
[01:19:07] all of these requests are made and the
[01:19:09] data is fetched. But, in case of GraphQL
[01:19:12] APIs, you have a single GraphQL
### chunk 120 [01:19:12]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

a is fetched. But, in case of GraphQL
[01:19:12] APIs, you have a single GraphQL[01:19:14] endpoint. So, the client specifies the
[01:19:16] shape of the response and this one
[01:19:19] endpoint handles all of the data
[01:19:20] interactions.
[01:19:22] It is still an HTTP request, but as you
[01:19:24] can see, we can specify the exact data
[01:19:26] that we need. For example, we need the
[01:19:28] user with ID 123 and we need only the
[01:19:31] name of the user, also posts, and from
[01:19:33] the posts, we can specify only title, so
[01:19:36] we don't need the images for this view.
[01:19:38] And again, with the comments, you can
[01:19:39] specify the exact data that you need
[01:19:42] within the object so that you are not
[01:19:43] doing over fetching of the data.
[01:19:46] Now, let's see the schema design and
### chunk 121 [01:19:46]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

doing over fetching of the data.
[01:19:46] Now, let's see the schema design and[01:19:48] type system of GraphQL and how it's
[01:19:50] different from RESTful APIs.
[01:19:52] The schema in this case is a contract
[01:19:54] between the client and server. In
[01:19:57] schema, first of all, you have types,
[01:19:58] which can be, for example, user type
[01:20:01] that you specify and you specify all the
[01:20:03] fields that exist on this user type,
[01:20:05] which are ID, name, posts, and so on.
[01:20:08] And as you can see, if the type is not a
[01:20:10] primitive type like posts, then you can
[01:20:12] specify another type of post array, and
[01:20:15] then this post type can be defined
[01:20:17] separately.
[01:20:18] Next, we have queries to read data. So,
[01:20:21] this is the equivalent of doing get
[01:20:23] requests in RESTful API. You specify the
### chunk 122 [01:20:23]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 the equivalent of doing get
[01:20:23] requests in RESTful API. You specify the[01:20:26] query and the function of this query.
[01:20:29] This can be the user query, which
[01:20:30] fetches the user with specific ID, and
[01:20:34] also the return type of this query,
[01:20:36] which in this case is the user type that
[01:20:38] we defined above.
[01:20:40] And GraphQL also come with mutations.
[01:20:42] You can think of this as the equivalent
[01:20:44] to post, put, patch, and delete methods
[01:20:47] in restful APIs. So, anytime you are
[01:20:50] mutating a data in the database, you are
[01:20:52] making a mutation query.
[01:20:55] Here, as you can see, we have an example
[01:20:56] of create user method, which accepts
[01:20:58] name and of course many things in real
[01:21:01] world, and then it returns the user type
[01:21:03] that we have defined above.
### chunk 123 [01:21:03]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 world, and then it returns the user type
[01:21:03] that we have defined above.[01:21:05] So, if you have good schema design in
[01:21:07] GraphQL, it should mirror your domain
[01:21:09] model, and it should be intuitive and
[01:21:11] flexible.
[01:21:12] Next, once you define the schema design
[01:21:15] and type system, you can start querying
[01:21:17] and mutating data with this GraphQL API.
[01:21:20] For that, we have queries for fetching
[01:21:22] data. Again, this is like the get
[01:21:24] requests in restful APIs, and here you
[01:21:27] can specify exactly what you need from
[01:21:29] the user. This is the same user method
[01:21:31] that we defined there in the schema. So,
[01:21:34] here you can also specify the exact
[01:21:36] attributes, like the name, posts, and
[01:21:38] from posts you need the title only. And
### chunk 124 [01:21:38]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

es, like the name, posts, and
[01:21:38] from posts you need the title only. And[01:21:41] this will make a request to your GraphQL
[01:21:43] API and return the exact data that you
[01:21:45] requested.
[01:21:46] Similarly, you can also use the
[01:21:48] mutations that you defined. For example,
[01:21:50] if you have a create post method defined
[01:21:52] as a mutation, you can use this to
[01:21:55] mutate the post, for example, setting
[01:21:57] the title and body of the post, and then
[01:22:00] you also specify what data you need to
[01:22:02] retrieve after this post is created,
[01:22:04] which is ID and title. When it comes to
[01:22:06] error handling in GraphQL APIs, this is
[01:22:09] a bit different than in restful APIs,
[01:22:12] since GraphQL always returns 200 OK
[01:22:14] status for all responses, even if there
### chunk 125 [01:22:14]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

GraphQL always returns 200 OK
[01:22:14] status for all responses, even if there[01:22:17] was an error. In this case, we have to
[01:22:19] return errors field in the response,
[01:22:21] which will indicate that there was an
[01:22:23] error. So, partial data can still be
[01:22:26] returned with errors, like in this case
[01:22:28] we have the user, which is null, and
[01:22:30] then we have the errors field, which
[01:22:31] indicates that you have the status code
[01:22:34] 404, message not found, and path, which
[01:22:36] is the user in your schema. As you can
[01:22:39] see in this case, you can specify the
[01:22:40] status code in the errors array. Since
[01:22:43] we are returning 200 status codes for
[01:22:45] all GraphQL requests, that's why we have
[01:22:48] the status code specifically mentioned
[01:22:50] in the errors, so that we know what kind
### chunk 126 [01:22:50]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 code specifically mentioned
[01:22:50] in the errors, so that we know what kind[01:22:52] of error this is, which is user not
[01:22:54] found. There are also best practices
[01:22:56] that we normally follow when designing
[01:22:58] GraphQL APIs. First of all, the schemas
[01:23:01] that we saw, it's a good practice to
[01:23:03] keep them small and modular. Also, we
[01:23:05] should avoid deeply nested queries. For
[01:23:08] example, you can have a user and then
[01:23:10] nested post, and then within the post
[01:23:12] you can have a comment, so this can be
[01:23:14] infinitely nested. And to avoid that, we
[01:23:17] usually implement query limits depths,
[01:23:19] which is how deep you can go, like how
[01:23:22] many layers nested you can have in your
[01:23:24] data. So, you specify something like six
[01:23:27] or seven layers deep. You also use
### chunk 127 [01:23:27]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

So, you specify something like six
[01:23:27] or seven layers deep. You also use[01:23:29] meaningful naming for types and fields,
[01:23:32] so that it also makes from the client
[01:23:34] side, because they both are going to use
[01:23:36] the same schema. And when mutating data,
[01:23:38] we always use the input types for
[01:23:41] mutations.
[01:23:42] Before a system can authorize or
[01:23:44] restrict anything, it first needs to
[01:23:46] know the identity of the requester,
[01:23:49] whether it's a user accessing our
[01:23:51] service through a browser or through
[01:23:54] mobile app, or it's a third-party
[01:23:57] service trying to access our system.
[01:23:59] That's what authentication does. It
[01:24:01] verifies that user or service trying to
[01:24:05] access our system is who they claim to
[01:24:07] be. But here is where most software
### chunk 128 [01:24:07]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

s our system is who they claim to
[01:24:07] be. But here is where most software[01:24:09] engineers confuse or mix up concepts.
[01:24:12] They mix up authentication methods with
[01:24:14] authorization frameworks. They treat JWT
[01:24:18] as an authentication method when in
[01:24:20] reality it's just a token format. They
[01:24:23] also confuse the bearer authentication
[01:24:25] with JWT. They sometimes call OAuth 2 an
[01:24:29] authentication method when in reality,
[01:24:31] it's actually an authorization
[01:24:33] framework. And they mix up single
[01:24:35] sign-on with authentication methods when
[01:24:38] it's really a user experience pattern.
[01:24:40] In this video, we're going to fix all of
[01:24:43] that by covering, first of all, what
[01:24:45] authentication is and then all the major
[01:24:47] types of authentication starting from
### chunk 129 [01:24:47]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ation is and then all the major
[01:24:47] types of authentication starting from[01:24:50] basic to digest authentication to API
[01:24:53] keys, sessions, and cookies, bearer
[01:24:55] authentication, and JWT tokens. What are
[01:24:58] access and refresh tokens? Also, we'll
[01:25:01] cover OAuth 2, OpenID Connect, also
[01:25:04] single sign-on and identity protocols,
[01:25:07] and understand what each one actually is
[01:25:09] and where this all fits.
[01:25:11] Let's first understand what is
[01:25:13] authentication, and then we'll get into
[01:25:15] the different authentication methods.
[01:25:17] So, authentication really answers one
[01:25:20] simple question, which is who the user
[01:25:22] is, whoever is trying to access our
[01:25:24] system. Let's say you have your system
[01:25:27] like your API gateway, the layer of
### chunk 130 [01:25:27]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

m. Let's say you have your system
[01:25:27] like your API gateway, the layer of[01:25:29] APIs, then your service layer, and also
[01:25:32] the data storage. Before anyone can make
[01:25:35] requests to your API gateway and start
[01:25:38] accessing services and data, they first
[01:25:41] need to be authenticated. That is where
[01:25:43] they send a login request. This comes
[01:25:47] either from a user or another service.
[01:25:50] This is where we confirm their identity
[01:25:52] if it's valid and grant access to our
[01:25:54] system, to our API gateway, and all the
[01:25:57] other services. Or if the identity is
[01:26:00] not confirmed, then we reject it with a
[01:26:02] 401 unauthorized response. This is the
[01:26:05] first step before they will get into the
[01:26:08] authorization, which is what they can
### chunk 131 [01:26:08]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

p before they will get into the
[01:26:08] authorization, which is what they can[01:26:10] access and what they can do once they
[01:26:13] can sign in to your system, but that's a
[01:26:16] separate discussion in itself. So in
[01:26:18] this one we are primarily focusing on
[01:26:20] the authentication and different
[01:26:23] authentication methods that we can use
[01:26:25] to verify the user's identity. Now let's
[01:26:27] see the different authentication methods
[01:26:30] that we have to verify the identity of
[01:26:33] the requester and let's start with the
[01:26:35] basic authentication methods. These are
[01:26:37] the basic of digest authentication, API
[01:26:40] keys and session based authentication.
[01:26:43] Let's start with the very first one on
[01:26:45] the list which is the basic
[01:26:47] authentication flow. This is the
### chunk 132 [01:26:47]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

1:26:45] the list which is the basic
[01:26:47] authentication flow. This is the[01:26:49] simplest form of authentication. Let's
[01:26:52] say you're making a request to the
[01:26:54] server to access some resource like
[01:26:56] API/users to retrieve the user data. You
[01:26:59] will first receive an unauthorized
[01:27:01] response because you didn't provide the
[01:27:04] credentials. So we prompt the user or
[01:27:06] the service to provide credentials
[01:27:08] before accessing any resource in the
[01:27:10] server. So in the upcoming request to
[01:27:13] the same resource they also provide the
[01:27:16] authorization header and this header
[01:27:19] contains the base 64 encoded version of
[01:27:22] the username and password for this user.
[01:27:26] This is where we verify it on the server
[01:27:28] side. If the credentials are valid then
### chunk 133 [01:27:28]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

re we verify it on the server
[01:27:28] side. If the credentials are valid then[01:27:30] we respond with 200 OK status with the
[01:27:34] user data returned in the body or we
[01:27:37] unauthorized it again marking this as
[01:27:40] credentials invalid. The problem with
[01:27:42] this method is that base 64 is easily
[01:27:46] reversible. So this is an insecure
[01:27:48] method unless it is wrapped with HTTPS
[01:27:51] protocol and even then it's rarely used
[01:27:54] nowadays in production outside of the
[01:27:57] internal tools because you're sending
[01:27:59] the credentials with every request and
[01:28:02] you're sending the base 64 encoded
[01:28:04] version which is not that secure. That's
[01:28:07] why we also have a digest authentication
[01:28:10] which is slightly better and it uses the
[01:28:13] MD5 hashing. So, this method works
### chunk 134 [01:28:13]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

is slightly better and it uses the
[01:28:13] MD5 hashing. So, this method works[01:28:16] similar to the authentication with basic
[01:28:19] version. So, you are let's say trying to
[01:28:21] access the same resource like the users.
[01:28:24] It will first respond with 401
[01:28:26] unauthorized prompting you to include
[01:28:29] the credentials and then you'll make the
[01:28:31] same request but with the hashed
[01:28:34] response and that will also contain the
[01:28:37] MD5 hash version instead of the plain
[01:28:40] password and username. And same process
[01:28:43] as the previous one. If the credentials
[01:28:46] are invalid, you will receive 401
[01:28:48] unauthorized. Otherwise, you will
[01:28:49] receive the successful response with the
[01:28:52] user data in the request body.
[01:28:54] This is slightly better than the basic
### chunk 135 [01:28:54]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

user data in the request body.
[01:28:54] This is slightly better than the basic[01:28:57] off as it uses the MD5 hashing, but it's
[01:29:00] still outdated and rarely used today
[01:29:03] because we have better options as you
[01:29:05] will see soon. And if you're wondering
[01:29:07] how do we set these options in the
[01:29:09] authorization, for instance, if you're
[01:29:11] making the request from Postman or if
[01:29:13] you're doing this from the code, then
[01:29:15] you'll include it as the header in the
[01:29:17] request. This is where you can set the
[01:29:19] authentication type and you will notice
[01:29:22] the things that we're discussing here
[01:29:23] like the basic authentication, which was
[01:29:25] the first version, or digest
[01:29:27] authentication, which is the second
[01:29:29] version, and you will see the other
### chunk 136 [01:29:29]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

thentication, which is the second
[01:29:29] version, and you will see the other[01:29:31] methods available here, also the API key
[01:29:34] option. And Postman calls all of these
[01:29:37] authentication types to just keep it
[01:29:39] simple on the interface, but that's also
[01:29:42] one of the reasons why developers get
[01:29:44] confused and they think that all of
[01:29:46] these are authentication types when some
[01:29:48] of them are authentication methods, some
[01:29:50] of them are authorization frameworks.
[01:29:53] Next, we have API key authentication.
[01:29:56] This is where you generate a unique key
[01:29:58] for each client and then they send it
[01:30:01] with each request to access the
[01:30:03] resources. So, for the same request as
[01:30:06] we discussed, the comes to your API
[01:30:08] server first and it will include either
### chunk 137 [01:30:08]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

cussed, the comes to your API
[01:30:08] server first and it will include either[01:30:11] authorization header or X-API-Key and
[01:30:15] that will include the API key that you
[01:30:17] generated for the user. These API keys
[01:30:20] are typically stored in a database with
[01:30:23] key hash and also the scopes for the API
[01:30:26] key. And for instance, if you ever tried
[01:30:29] to access APIs by generating a key on
[01:30:32] the dashboard and then it gives you the
[01:30:35] key back which you can attach to the
[01:30:37] requests. That is where you already used
[01:30:40] the API key of that service to access
[01:30:42] the data. So, if you included that key
[01:30:45] in the request, then the server will
[01:30:48] first do an API key lookup in the
[01:30:50] permissions or users table. And if it's
[01:30:53] able to verify that the API key is
### chunk 138 [01:30:53]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ssions or users table. And if it's
[01:30:53] able to verify that the API key is[01:30:55] valid, then we will authorize the
[01:30:57] request and send the successful response
[01:31:00] with the data in the response body.
[01:31:02] Otherwise, the user will get a 401
[01:31:05] unauthorized response.
[01:31:07] And if the key is missing overall, like
[01:31:10] the authorization header or X-API-Key,
[01:31:13] then we just return a 400 bad request
[01:31:15] because the API key is required to
[01:31:18] access this type of system.
[01:31:20] One issue with API keys is that if the
[01:31:22] key ever leaks, then anyone can use it
[01:31:25] and start accessing the resources on
[01:31:28] your behalf with your API key and there
[01:31:31] is no built-in expiration unless you
[01:31:34] implement it yourself. Another thing is
### chunk 139 [01:31:34]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

uilt-in expiration unless you
[01:31:34] implement it yourself. Another thing is[01:31:36] that this might seem similar to JSON web
[01:31:39] tokens, but API keys are just random
[01:31:42] strings with no embedded information
[01:31:45] while in JWT, we can store also
[01:31:47] information as you will see shortly. So,
[01:31:50] the server here has no way to know who
[01:31:53] owns the key or what permissions they
[01:31:55] have without looking it up in the
[01:31:56] database.
[01:31:58] Next, we have the traditional web
[01:32:00] approach which is the session-based
[01:32:02] authentication. This is where a user
[01:32:05] logs in with their credentials, and then
[01:32:08] we create a session in some sort of
[01:32:10] session storage. This session storage
[01:32:12] can be as simple as just in memory, like
[01:32:15] just a variable, but the problem here is
### chunk 140 [01:32:15]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

mple as just in memory, like
[01:32:15] just a variable, but the problem here is[01:32:18] that we will lose it once the server
[01:32:20] restarts or crashes. The other option is
[01:32:23] we can use tools like Redis, which is
[01:32:25] one of the most common ones in
[01:32:27] production because it's fast and it
[01:32:29] supports expiration for the sessions, or
[01:32:32] we can use a dedicated database here,
[01:32:35] like SQL type of database. Another
[01:32:38] option, which is very rare, is to use
[01:32:40] the file system of the server that
[01:32:42] you're using. The problem with this one
[01:32:45] is that it's not scalable, and overall
[01:32:47] Redis is usually the go-to for
[01:32:49] production because it's fast and has
[01:32:52] built-in key expiration. So, with the
[01:32:54] first request, we are fetching the
### chunk 141 [01:32:54]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

lt-in key expiration. So, with the
[01:32:54] first request, we are fetching the[01:32:56] session ID, and then we set the session
[01:32:58] cookie on the client side. Then for any
[01:33:02] other upcoming requests that contain
[01:33:04] this cookie, we look up the session in
[01:33:06] the session storage here, and then if
[01:33:09] the session is valid, we will get back
[01:33:11] the user data, and we will send it with
[01:33:13] authorized response. Otherwise, if it's
[01:33:16] not found, if we can't find the session,
[01:33:18] then this user is not authenticated, so
[01:33:20] we send them an unauthorized response.
[01:33:22] One challenge with session-based
[01:33:24] authentications is that it is stateful,
[01:33:26] which means that the server must
[01:33:28] remember the sessions. We need to have
[01:33:30] some sort of session storage here, and
### chunk 142 [01:33:30]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 the sessions. We need to have
[01:33:30] some sort of session storage here, and[01:33:33] it works great for traditional web apps,
[01:33:36] but cannot scale as easily for APIs or
[01:33:39] distributed systems. Now, let's look at
[01:33:41] token-based authentication. We'll cover
[01:33:44] bearer authentication, JWT tokens,
[01:33:46] access and refresh tokens, and how this
[01:33:49] compares to the session-based
[01:33:51] authentication. Instead of sessions,
[01:33:53] modern applications usually use tokens.
[01:33:56] So, the client sends a token with each
[01:33:59] request. For example, we have a login
[01:34:01] with credentials, where user will
[01:34:04] include their credentials in the
[01:34:06] authorization header, which will include
[01:34:08] the type of authentication, which is
[01:34:10] bearer, and also the token, which we
### chunk 143 [01:34:10]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

type of authentication, which is
[01:34:10] bearer, and also the token, which we[01:34:13] will validate on the server side. One
[01:34:15] thing developers confuse here is the
[01:34:17] bearer token and JSON web tokens. Bearer
[01:34:20] token just means whoever has this token
[01:34:23] gets access. So, it's a pattern, but not
[01:34:26] a specific method. And the most common
[01:34:28] type of bearer token is JWT, JSON web
[01:34:32] token.
[01:34:33] It's basically a signed JSON object that
[01:34:36] contains the user ID or email for us to
[01:34:40] validate the user, also expiration time,
[01:34:43] and other claims as we need to store
[01:34:45] them, like roles, permissions, and so
[01:34:47] on. So, what we do on the authentication
[01:34:50] server is we validate the credentials
[01:34:52] once we receive that authorization
### chunk 144 [01:34:52]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ver is we validate the credentials
[01:34:52] once we receive that authorization[01:34:54] header. And it is stateless, meaning
[01:34:57] that we don't need a database here to
[01:34:59] look up, and that is why it's also
[01:35:01] scalable compared to the session-based
[01:35:04] authentication. Before the JWT, let's
[01:35:07] say revolution, a token was just a
[01:35:10] string with no information. And that
[01:35:13] token was sent, and then this was looked
[01:35:15] up in some sort of database, and only
[01:35:18] then we could verify that the user has
[01:35:20] access. The downside of that was that,
[01:35:23] of course, it's still stateful, because
[01:35:25] we need the database access or cache,
[01:35:28] which is required every time the token
[01:35:30] is used.
[01:35:31] With JSON web tokens, now we can encode
### chunk 145 [01:35:30]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

the token
[01:35:30] is used.
[01:35:31] With JSON web tokens, now we can encode[01:35:34] and verify via signing their own claims.
[01:35:37] And this is what now allows us to issue
[01:35:40] a short-lived JWT tokens that are
[01:35:42] stateless, meaning they are
[01:35:44] self-contained, and they don't depend on
[01:35:47] anybody else. They do not need to hit
[01:35:50] the database, and this reduces the
[01:35:53] databases load and it also simplifies
[01:35:55] the authentication process for the
[01:35:57] server. So the first time you will
[01:36:00] receive the credentials and validate the
[01:36:02] user and if it is valid we will generate
[01:36:04] the JSON web token and send it to the
[01:36:07] client. From this point forward the
[01:36:10] client can make requests and include
[01:36:12] this better token which is this
### chunk 146 [01:36:12]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 client can make requests and include
[01:36:12] this better token which is this[01:36:14] authorization header that contains the
[01:36:17] better authentication with the token.
[01:36:20] And that token is most cases it is a
[01:36:22] JSON web token. We verify that signature
[01:36:26] locally without needing to hit the
[01:36:28] database and if the token is valid we
[01:36:31] return the requested data otherwise we
[01:36:33] return an unauthorized response.
[01:36:36] Modern systems also use two types of
[01:36:38] tokens. One of them is the access token
[01:36:42] and the other one is the refresh tokens.
[01:36:45] The reason we need two tokens here is
[01:36:47] that access tokens are short-lived and
[01:36:49] they are used for API calls to the
[01:36:51] server while the refresh tokens are
[01:36:54] long-lived and they are used to get new
### chunk 147 [01:36:54]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 while the refresh tokens are
[01:36:54] long-lived and they are used to get new[01:36:57] access tokens basically to renew the
[01:37:00] access token.
[01:37:01] Whenever user sends a login request and
[01:37:04] signs in they get both of these tokens.
[01:37:07] We generate an access token that's valid
[01:37:09] for 15 minutes to 1 hour and we generate
[01:37:13] a refresh token that can last for days
[01:37:16] or even weeks.
[01:37:17] Client now will use the access token to
[01:37:20] access the API and make the requests and
[01:37:24] it also stores the refresh tokens. One
[01:37:26] important note here is that we never
[01:37:28] store it in local storage but we store
[01:37:31] it in HTTP only cookies. This prevents
[01:37:34] us from excess attacks on the client
[01:37:37] side.
[01:37:38] And after this user will stay logged in
### chunk 148 [01:37:37]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

n the client
[01:37:37] side.
[01:37:38] And after this user will stay logged in[01:37:41] without re-entering credentials. If
[01:37:43] their access token expires they will get
[01:37:46] an unauthorized response And this is
[01:37:48] where we will use that refresh token
[01:37:50] which we stored to generate a new access
[01:37:53] token on the off server side. We can
[01:37:56] make a request with that new token, and
[01:37:58] this will successfully return us the
[01:38:00] data since we renewed the access token.
[01:38:03] Next, let's get into OAuth 2 and OpenID
[01:38:07] Connect, which are some of the
[01:38:09] misunderstood concepts, and let's
[01:38:12] clarify whether these are authentication
[01:38:14] methods or authorization frameworks and
[01:38:17] how they work. OAuth 2 is one of the
[01:38:19] concepts that is often misunderstood.
### chunk 149 [01:38:19]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

hey work. OAuth 2 is one of the
[01:38:19] concepts that is often misunderstood.[01:38:22] It's an authorization framework and not
[01:38:24] an authentication. So, it answers what
[01:38:27] can this app access on behalf of the
[01:38:30] user.
[01:38:31] For instance, if you want to grant an
[01:38:33] application access to your Google Drive
[01:38:35] to be able to read your files from
[01:38:38] there, you would typically connect your
[01:38:40] Google Drive for this external
[01:38:43] application.
[01:38:44] And you're giving the app permission to
[01:38:46] access your data. The way it works is it
[01:38:49] first will redirect you to consent
[01:38:52] screen from the Google OAuth
[01:38:54] authentication, and it will show you the
[01:38:56] permission request. And if you allow
[01:38:59] access for this application to be able
### chunk 150 [01:38:59]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

sion request. And if you allow
[01:38:59] access for this application to be able[01:39:03] to read the drive files on your behalf,
[01:39:06] then it will return the authorization
[01:39:08] code to this external application, or it
[01:39:10] can also be your application.
[01:39:13] And the way it works after that is that
[01:39:15] you exchange the code for token, and you
[01:39:18] return the access token from Google
[01:39:21] OAuth to be able to read the data.
[01:39:24] That is the confusing part because
[01:39:25] you're getting back an access token for
[01:39:28] the Google Drive API, and you might
[01:39:30] think that this is an authentication
[01:39:32] method, but the access token just proves
[01:39:35] that the app can access your resources.
[01:39:39] But it doesn't tell the app who you are.
[01:39:41] It just proves that the app is allowed
### chunk 151 [01:39:41]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

sn't tell the app who you are.
[01:39:41] It just proves that the app is allowed[01:39:43] to access certain resources from your
[01:39:46] Google Drive. So, after this point, the
[01:39:48] application will be able to request
[01:39:50] files with that token and return the
[01:39:53] user files from Google Drive API.
[01:39:56] Next, we have OpenID Connect, which adds
[01:39:59] authentication on top of OAuth 2.
[01:40:02] So, when you click on sign in to Google,
[01:40:04] let's say, via your app, it will
[01:40:07] redirect you to the authorization
[01:40:09] endpoint. And this will show you the
[01:40:12] login screen where you grant access to
[01:40:14] sign in to Google through your
[01:40:16] application. If you enter your
[01:40:18] credentials and consent, then the
[01:40:20] provider will return the authorization
[01:40:23] code. And after this step, your
### chunk 152 [01:40:23]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

rovider will return the authorization
[01:40:23] code. And after this step, your[01:40:25] application will exchange the code for
[01:40:28] tokens and return the access token in
[01:40:31] combination with the ID token.
[01:40:33] From here, the access token is for OAuth
[01:40:36] 2 authorization, but the ID token is a
[01:40:39] JSON web token that contains your
[01:40:41] identity, which includes your email or
[01:40:44] username user ID.
[01:40:46] Which means that after this point, your
[01:40:48] application is able to verify the
[01:40:51] signature and extract the user's
[01:40:54] identity to send the ID token for
[01:40:56] verification to your backend.
[01:40:59] And by having this ID token, your
[01:41:01] application can now create its own
[01:41:03] session and grant the access token for
[01:41:06] that user.
### chunk 153 [01:41:03]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 its own
[01:41:03] session and grant the access token for
[01:41:06] that user.[01:41:08] This is a modern solution. It's secure
[01:41:10] and also scales well. And that's also
[01:41:13] why most applications nowadays use that
[01:41:15] type of authentication like sign in with
[01:41:18] Google, GitHub, Microsoft, and so on.
[01:41:20] And lastly, let's cover single sign-on
[01:41:23] and identity protocols.
[01:41:25] Single sign-on is a user experience, not
[01:41:28] an authentication method. Which means
[01:41:30] that you're able to log in once, but
[01:41:33] access multiple services. For example,
[01:41:35] when you want to log into Google or
[01:41:38] Okta, let's say you want to get access
[01:41:40] to your Gmail, to your Google Drive, to
[01:41:43] YouTube, to Google Calendar, you can do
[01:41:46] this by logging in once to the identity
### chunk 154 [01:41:46]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

o Google Calendar, you can do
[01:41:46] this by logging in once to the identity[01:41:50] provider. Let's say it can be Google in
[01:41:52] this case if you want to access these
[01:41:54] services.
[01:41:55] And single sign-on uses identity
[01:41:58] protocols underneath to validate these
[01:42:01] sessions. So, once you sign in with the
[01:42:04] identity provider, let's say it's Google
[01:42:06] in this case, your global session is
[01:42:09] stored in a session storage. And then
[01:42:11] you get back a single sign-on cookie to
[01:42:14] your client to be able to access other
[01:42:16] resources. So, let's say you want to
[01:42:18] access Gmail for the first time, then
[01:42:21] once you log in, you verify also the
[01:42:24] session and now you're able to access
[01:42:26] Gmail. And for the next request, if you
### chunk 155 [01:42:26]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

and now you're able to access
[01:42:26] Gmail. And for the next request, if you[01:42:29] need to access Google Drive for the next
[01:42:31] one, you don't need to log in again
[01:42:33] because you have these cookie and the
[01:42:35] session stored in the session storage.
[01:42:37] So, we just verify your session and if
[01:42:40] it's valid, then you get access to
[01:42:42] Google Drive as well. And similarly to
[01:42:44] YouTube, to Google Calendar and other
[01:42:46] services.
[01:42:47] As I mentioned, single sign-on uses
[01:42:50] identity protocols underneath. And these
[01:42:53] protocols are SAML, which is Security
[01:42:56] Assertion Markup Language, or OpenID
[01:42:59] Connect. Both of these are identity
[01:43:02] protocols which are used in combination
[01:43:04] with single sign-on.
[01:43:06] In case of SAML, to be able to access
### chunk 156 [01:43:04]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

[01:43:04] with single sign-on.
[01:43:06] In case of SAML, to be able to access[01:43:09] the app, you're redirected to login and
[01:43:11] this is where we use SAML for
[01:43:13] authentication.
[01:43:14] This is a common solution in enterprise
[01:43:17] and legacy systems like Salesforce,
[01:43:20] corporate dashboards, and so on. It is
[01:43:22] an XML-based protocol, so once you want
[01:43:26] to sign in, you are redirected to login
[01:43:29] and then you get back the SAML assertion
[01:43:31] in XML format. And after that, your
[01:43:34] identity is confirmed for the user, and
[01:43:37] now you're able to access the
[01:43:40] third-party application.
[01:43:42] SAML is still widely used, but it's an
[01:43:44] older version compared to OpenID
[01:43:47] Connect. So, the next option is the
[01:43:49] OpenID Connect as an identity protocol.
### chunk 157 [01:43:49]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

t. So, the next option is the
[01:43:49] OpenID Connect as an identity protocol.[01:43:52] Let's say you want to access an app, and
[01:43:54] in this case it's Gmail.
[01:43:56] You will be redirected to login to
[01:43:58] provide your credentials. And once you
[01:44:01] provide your credentials, the user is
[01:44:03] authenticated, and now you get back the
[01:44:06] ID token in JSON Web Token format. And
[01:44:10] this is what you will use for confirming
[01:44:12] your identity with Gmail.
[01:44:15] This is, for instance, what Google uses
[01:44:17] under the hood, and it's a more modern
[01:44:20] approach compared to SAML, but both of
[01:44:22] them are still very secure and relevant.
[01:44:26] These are the most common types of
[01:44:27] authentication, and that is just the
[01:44:30] first step for accessing our system.
### chunk 158 [01:44:30]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

entication, and that is just the
[01:44:30] first step for accessing our system.[01:44:32] After you know who the user is with
[01:44:35] authentication, you need to also know
[01:44:37] what they can do and what permissions
[01:44:39] they have. The authentication is just
[01:44:41] the first step before users can access
[01:44:43] your service. So, this tells you who the
[01:44:46] user is, and if they are allowed to
[01:44:48] access your service. That is when they
[01:44:50] send a login request, and you confirm or
[01:44:53] deny their identity. But after that, you
[01:44:56] also have the authorization step, which
[01:44:58] tells you what resources exactly this
[01:45:00] user can access to. Basically, it tells
[01:45:03] you what they can do, what the user can
[01:45:05] do in your system. And that is what we
[01:45:07] will cover next in the next video.
### chunk 159 [01:45:07]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

n your system. And that is what we
[01:45:07] will cover next in the next video.[01:45:10] Authorization is the step that happens
[01:45:12] after authentication, once someone is
[01:45:15] logging in into our system. So, once
[01:45:17] their login request is approved, which
[01:45:19] means that the system now knows who the
[01:45:21] user is, the next step is deciding what
[01:45:24] they can do, which is the step of
[01:45:26] authorization. It needs to check what
[01:45:28] resources or actions that user has
[01:45:30] permissions to access and also what are
[01:45:32] the denied actions for this user. This
[01:45:35] is how we control security and privacy
[01:45:37] in the systems and in this video you'll
[01:45:40] learn how the applications and systems
[01:45:42] manage permissions using the three main
[01:45:44] authorization models. The first one is
### chunk 160 [01:45:44]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

rmissions using the three main
[01:45:44] authorization models. The first one is[01:45:47] role-based access control. Next, we have
[01:45:49] attribute-based access control. Also,
[01:45:52] access control list, which is another
[01:45:53] way of managing authorization. Plus, you
[01:45:56] learn how technologies like OAuth 2 and
[01:45:58] JWTs help us to enforce those rules in
[01:46:01] practice. So, authentication happens
[01:46:03] first, which tells us who the user is
[01:46:06] and if they are allowed to access our
[01:46:08] system. But, on the next step we have
[01:46:10] authorization, which determines what you
[01:46:12] can actually do as a user in this
[01:46:14] system. If we take a look at GitHub as
[01:46:17] an example and accessing repositories on
[01:46:20] GitHub, there you have different
[01:46:21] permissions for different users. For
### chunk 161 [01:46:21]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

GitHub, there you have different
[01:46:21] permissions for different users. For[01:46:23] example, user A can have write access
[01:46:26] only, which means they can only push
[01:46:28] code to this repo. But, on the other
[01:46:30] hand, we can have user B and here you
[01:46:32] can grant only read access, which means
[01:46:34] they can only read this repository, but
[01:46:37] they cannot push code to it or they
[01:46:39] cannot create pull requests and so on.
[01:46:41] And on the other side, we can have also
[01:46:43] admin users, which have full control, so
[01:46:46] they can manage all the settings for the
[01:46:48] repository. They can even decide to
[01:46:50] delete this repository and so on. So,
[01:46:53] you can see that different users can
[01:46:54] have different access controls on
[01:46:57] systems. To manage these access
### chunk 162 [01:46:57]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

54] have different access controls on
[01:46:57] systems. To manage these access[01:46:59] controls, we have common authorization
[01:47:01] models. So, the one that we just looked
[01:47:03] at is the role-based authentication
[01:47:06] model, which assigns roles to users,
[01:47:08] something like admin, editor, or
[01:47:10] read-only access, write-only access. And
[01:47:13] this is the most common approach among
[01:47:15] these authorization models. But, we also
[01:47:18] have attribute-based access control,
[01:47:20] which is based on the user or resource
[01:47:23] attributes. So, this is more flexible
[01:47:25] and more complex compared to the
[01:47:28] role-based authentication. And the other
[01:47:30] common approach is to have access
[01:47:32] control lists, ACL, and each resource
[01:47:35] here has its own permissions list. So,
### chunk 163 [01:47:35]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 lists, ACL, and each resource
[01:47:35] here has its own permissions list. So,[01:47:37] you can assign permission lists to a
[01:47:39] resource, and this is what will
[01:47:41] determine what resources you can access.
[01:47:43] For example, this is a common way of
[01:47:45] managing Google Docs, and we will look
[01:47:47] at this in more detail now. And each of
[01:47:50] these models has its tradeoffs, pros and
[01:47:53] cons. So, this depends on the specific
[01:47:55] system requirements, but real systems
[01:47:58] often combine also multiple models
[01:48:00] together to have more complex and more
[01:48:03] secure setup. So, first up we have
[01:48:05] role-based access control, or RBAC as an
[01:48:09] acronym. Here, users are assigned to
[01:48:11] roles, and each role has a defined set
[01:48:14] of permissions. For example, as you saw
### chunk 164 [01:48:14]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

d each role has a defined set
[01:48:14] of permissions. For example, as you saw[01:48:16] with the GitHub, you can have admins,
[01:48:18] and admins usually have full access to
[01:48:20] all resources. So, they can create, they
[01:48:23] can read, or update resources. They can
[01:48:25] even delete resources, and also manage
[01:48:28] other users in the roles. And next, you
[01:48:30] have editor, which is usually a bit less
[01:48:33] than admin. So, they can edit content
[01:48:36] like creating or reading content or
[01:48:38] updating resources, but they cannot
[01:48:41] delete resources, and they cannot also
[01:48:43] manage other users.
[01:48:45] And next, you can have viewer users,
[01:48:47] which can only read data. So, they can
[01:48:49] read the resources and content, but they
[01:48:52] cannot update anything, or they cannot
### chunk 165 [01:48:52]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

esources and content, but they
[01:48:52] cannot update anything, or they cannot[01:48:54] create anything in your system.
[01:48:56] This is the most common way in
[01:48:58] authorization models, and this is used
[01:49:01] in apps that you use daily, like you saw
[01:49:03] with GitHub or Stripe dashboards or CMS
[01:49:06] tools, team management tools, and so on.
[01:49:09] The next model is attribute-based access
[01:49:12] control, or ABAC in short. This access
[01:49:15] control goes beyond the roles, so it
[01:49:18] uses the user attributes or resource
[01:49:21] attributes and environment conditions to
[01:49:23] define the access. Some example policy
[01:49:26] you can see here. Let's say you want to
[01:49:28] only allow access if some conditions are
[01:49:31] met. In this case, whenever the user
[01:49:33] department is set to HR and you can
### chunk 166 [01:49:33]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

. In this case, whenever the user
[01:49:33] department is set to HR and you can[01:49:35] combine this with multiple conditions
[01:49:37] like whenever the resource attribute
[01:49:40] equals to internal and so on and only in
[01:49:43] this case you allow them access. And you
[01:49:45] either allow them read access or write
[01:49:47] access, so this can also be combined
[01:49:49] with the role-based authorization.
[01:49:52] But in this case you are checking the
[01:49:54] user model or resource model in your
[01:49:57] database and based on the attributes you
[01:49:59] either allow or deny the access. So here
[01:50:03] as you can see we are checking user
[01:50:04] attributes like the department, the age
[01:50:07] or whatever you want to check here. Next
[01:50:10] you can also combine it with resource
[01:50:12] attributes like confidentiality or the
### chunk 167 [01:50:12]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 also combine it with resource
[01:50:12] attributes like confidentiality or the[01:50:14] owner of the resource or classification.
[01:50:18] And this can also be combined with
[01:50:20] environment like time of the day,
[01:50:22] location, device type and so on.
[01:50:24] Since you're combining these attributes
[01:50:26] to either grant or restrict access, this
[01:50:29] is more flexible than the role-based
[01:50:31] authorization, but it requires good
[01:50:33] policy management and generally it's
[01:50:36] more complex and you can encounter
[01:50:38] conflicts here with the attribute-based
[01:50:40] access control. The third common type is
[01:50:43] the access control list. Instead of
[01:50:45] providing role-based access or
[01:50:47] attribute-based access, you can have
[01:50:49] access control list for the specific
### chunk 168 [01:50:49]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ibute-based access, you can have
[01:50:49] access control list for the specific[01:50:51] resource. Let's say you have a resource
[01:50:54] like a document or a JSON file. And here
[01:50:57] you can have a permission list on which
[01:50:59] users can access this document. Like
[01:51:02] user Alyssa has only read access or user
[01:51:05] Bob has both read and write access and
[01:51:08] another user has no access to this
[01:51:10] document. So as you can see, we're
[01:51:12] managing two things here. First of all,
[01:51:14] which users are allowed to access this
[01:51:17] document, and second, what are their
[01:51:19] permissions? So, each of the users has
[01:51:22] different permissions on this document.
[01:51:24] ACLs are highly specific and also
[01:51:27] user-centric, which means it's hard to
[01:51:29] scale them well in systems with millions
### chunk 169 [01:51:29]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ic, which means it's hard to
[01:51:29] scale them well in systems with millions[01:51:32] of users or objects unless you manage
[01:51:35] them carefully. But, for example, Google
[01:51:38] Drive is one example of this where you
[01:51:40] have documents like a Google Doc, and
[01:51:43] then you share this Google Doc with your
[01:51:45] colleagues, right? So, you share someone
[01:51:47] with read access only, and then you
[01:51:49] share this Doc with someone else, but
[01:51:51] now they can also edit and add comments
[01:51:54] to this document. So, this is a example
[01:51:57] of ACL, access control list, which is
[01:52:00] used in Google Drive and Google
[01:52:02] Documents. This gives you more control
[01:52:05] over resources and documents, but it's
[01:52:07] also harder to scale with millions of
[01:52:10] users, but it's possible, as you can
### chunk 170 [01:52:10]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

harder to scale with millions of
[01:52:10] users, but it's possible, as you can[01:52:11] see, because Google Drive is using this
[01:52:13] for their documents, Excel sheets, and
[01:52:16] so on.
[01:52:17] So, these were the access control
[01:52:19] models, but how do systems enforce those
[01:52:22] authorizations? This are where OAuth 2
[01:52:24] and JWT or access tokens come into play.
[01:52:28] So, first we have OAuth 2, which is
[01:52:30] delegated authorization, which is a
[01:52:33] protocol used when service wants to
[01:52:35] access another service's resources on a
[01:52:38] behalf of a user. For example, if you
[01:52:40] want to let a third-party app read your
[01:52:43] GitHub repositories, let's say you're
[01:52:45] deploying your app to Vercel, so you
[01:52:48] need to give Vercel control over your
### chunk 171 [01:52:48]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ying your app to Vercel, so you
[01:52:48] need to give Vercel control over your[01:52:50] repository on GitHub. Instead of giving
[01:52:53] your username and password to the
[01:52:55] third-party application, which won't be
[01:52:58] secure at all because you don't know
[01:53:00] what they can do with your username and
[01:53:02] password, this way you are giving them
[01:53:03] full control. Instead, GitHub gives them
[01:53:06] the token that represents the
[01:53:08] permissions which you approved to use.
[01:53:11] So, you as a user sign the request with
[01:53:13] the third-party app to request access to
[01:53:17] your repositories, and then GitHub gives
[01:53:19] you the access token which you should
[01:53:21] create. So, you should also provide what
[01:53:24] resources, what repositories this
[01:53:26] third-party app can access, and also
### chunk 172 [01:53:26]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

esources, what repositories this
[01:53:26] third-party app can access, and also[01:53:28] what they can do. Can they create, read,
[01:53:31] update, or can they delete, or whatever
[01:53:33] the permissions you set? And then GitHub
[01:53:35] sends them the token which contains the
[01:53:38] permissions which this third-party app
[01:53:40] is allowed to use. And OAuth2 defines
[01:53:42] the flow for securely issuing and
[01:53:45] validating those tokens. So, you give
[01:53:47] them the access token and not your
[01:53:50] password which represents the
[01:53:51] permissions that you approved
[01:53:53] personally. So, it can be reading
[01:53:55] specific repos or also creating, pushing
[01:53:58] to those repositories, but not deleting
[01:54:00] those repositories. And next, we have
[01:54:03] also token-based authorization using JWT
### chunk 173 [01:54:03]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ositories. And next, we have
[01:54:03] also token-based authorization using JWT[01:54:06] or bearer tokens and permission logic.
[01:54:09] Once a user is authenticated, most
[01:54:11] systems use a token, typically a JWT
[01:54:14] token, or this can be also bearer token
[01:54:17] that carries this information like user
[01:54:19] ID, the roles like admin or editor, and
[01:54:22] also scopes which is what scopes they
[01:54:25] are allowed to access, and whenever this
[01:54:28] token is expiring and who is the issuer
[01:54:31] of this token. So, whenever a user makes
[01:54:33] a request, it always carries this token
[01:54:36] information and reaches to the backend
[01:54:38] server. This is where the server will
[01:54:40] check your token and validity, and it
[01:54:43] will apply the appropriate permission
[01:54:45] logic. So, to not confuse this with
### chunk 174 [01:54:45]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 apply the appropriate permission
[01:54:45] logic. So, to not confuse this with[01:54:47] authorization models, there is a key
[01:54:49] distinction. The token usually carries
[01:54:51] the identity and claims of your user as
[01:54:54] you see it here, but authorization
[01:54:56] models like role-based or
[01:54:58] attribute-based, this is what defines
[01:55:01] what is allowed to access as a user. So,
[01:55:04] tokens are just mechanisms while these
[01:55:06] are authorization models. So, in
[01:55:09] summary, authorization isn't just
[01:55:11] letting users in like authentication,
[01:55:13] but it also controls what they can
[01:55:15] access once they are in.
[01:55:17] We learned what authorization is, what
[01:55:19] are the three most common authorization
[01:55:21] models, which are role-based,
[01:55:23] attribute-based, and access control
### chunk 175 [01:55:23]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

21] models, which are role-based,
[01:55:23] attribute-based, and access control[01:55:25] lists, and also you saw couple of
[01:55:27] real-world examples like how GitHub
[01:55:29] manages your authorization tokens, and
[01:55:32] it should give you an idea on when to
[01:55:34] use each model based on the system that
[01:55:36] you're building. And you also saw some
[01:55:38] implementation patterns with OAuth 2 or
[01:55:41] JWT tokens. Each of these models has
[01:55:44] their own trade-offs, their own pros and
[01:55:46] cons, and real systems often combine
[01:55:48] multiple models to stay flexible and
[01:55:51] secure. APIs are like doors into your
[01:55:54] system. If you leave them unprotected,
[01:55:56] then attackers and anyone can walk right
[01:55:59] in and do whatever they want with your
[01:56:01] user data and overall the system. That's
### chunk 176 [01:56:01]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

whatever they want with your
[01:56:01] user data and overall the system. That's[01:56:04] why in today's video we'll look at seven
[01:56:06] proven techniques which will help you to
[01:56:07] protect your APIs from unwanted attacks.
[01:56:11] The first one we have in the list is
[01:56:12] rate limiting, which controls how many
[01:56:15] requests a client can make in a given
[01:56:17] time. For example, you can set a limit
[01:56:20] for user A to make, let's say, 100
[01:56:23] requests per some period of time to your
[01:56:26] API. And if they cross that limit and,
[01:56:28] let's say, make 100 and one request,
[01:56:30] then you block the next request and
[01:56:33] allow some time to pass before they can
[01:56:35] send their next request. If you don't
[01:56:38] set this to your API, then attackers can
[01:56:40] overwhelm your system. They can send
### chunk 177 [01:56:40]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 to your API, then attackers can
[01:56:40] overwhelm your system. They can send[01:56:42] like thousands of requests per minute
[01:56:45] and then overwhelm your API, which will
[01:56:47] take your system down, or it can also
[01:56:49] brute force your data. And these rate
[01:56:51] limits can be set per endpoint. For
[01:56:54] instance, let's say you have some
[01:56:55] {slash} comments endpoint, and here they
[01:56:58] can send a request to either create a
[01:57:00] comment or fetch comments. You can set
[01:57:02] that limit for endpoint level. So, these
[01:57:05] comments endpoint will be set to some
[01:57:08] strict number of requests per minute.
[01:57:11] You can also set it per user or IP
[01:57:13] address. Let's say in A we have the IP
[01:57:16] address of first user, and then B for
[01:57:18] the second, C for this one, and your
### chunk 178 [01:57:18]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ss of first user, and then B for
[01:57:18] the second, C for this one, and your[01:57:20] attacker has some IP address which
[01:57:22] corresponds to D.
[01:57:24] If you get the 101st request from the D
[01:57:28] IP address, then you will know that this
[01:57:30] user overused the API, so you will block
[01:57:34] it at the user IP level.
[01:57:36] And there is also overall rate limiting
[01:57:38] to protect from DDoS attacks. Since you
[01:57:41] can set the rate limit to work per user
[01:57:44] or per IP address, that means that this
[01:57:46] attacker alone cannot send that many
[01:57:48] requests. You will block it with your
[01:57:51] rate limiting in the API. But what they
[01:57:53] can do is they can spin up some bots,
[01:57:56] and each bot will have their own limit,
[01:57:58] right? Let's say you've set it to 100
### chunk 179 [01:57:58]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 bot will have their own limit,
[01:57:58] right? Let's say you've set it to 100[01:58:00] per IP address. So, each of these bots
[01:58:03] has 100, and overall they have more than
[01:58:06] you would allow or your system could
[01:58:08] handle. That's why you have also overall
[01:58:11] rate limitings, which can be some bigger
[01:58:13] number. So, whenever all the traffic
[01:58:16] coming into your server reaches or
[01:58:18] passes this number, then you will
[01:58:20] temporarily block all requests until you
[01:58:23] find out the root cause. And of course,
[01:58:25] these numbers are just examples, so in
[01:58:27] reality it's much more than 1,000, but
[01:58:30] that's just an example. The second one
[01:58:32] on the list is CORS, which stands for
[01:58:34] cross-origin resource sharing. This
[01:58:37] controls which domain can call your API
### chunk 180 [01:58:37]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

origin resource sharing. This
[01:58:37] controls which domain can call your API[01:58:40] from a browser, and without proper CORS,
[01:58:42] malicious websites could trick users'
[01:58:45] browsers into making requests on their
[01:58:47] behalf. For instance, if your API is
[01:58:50] only meant to serve your front end up,
[01:58:53] which is that up.yourdomain.com,
[01:58:56] then only requests from this source
[01:58:58] should be allowed. If anyone else sends
[01:59:01] you a request like up.anotherdomain.com,
[01:59:04] then you should block this request and
[01:59:06] not allow them to use your API for
[01:59:08] authenticating or using any of its data.
[01:59:12] The third one is also a common one,
[01:59:14] which is SQL and no SQL injections.
[01:59:17] Injection attacks can happen when the
[01:59:19] user input is directly included in the
### chunk 181 [01:59:19]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

on attacks can happen when the
[01:59:19] user input is directly included in the[01:59:21] database query. For instance, attacker
[01:59:23] can modify it and send some queries to
[01:59:27] read or delete your data.
[01:59:29] Here, for example, this part bypasses
[01:59:31] the checks entirely and then attacker
[01:59:34] can use this query to start reading data
[01:59:36] from your database or modify anything,
[01:59:39] or they can also delete all the data,
[01:59:41] all the user data, and any other tables
[01:59:44] that you have in this database.
[01:59:46] So, to fix this, we always use
[01:59:48] parameterized queries or ORM safeguards.
[01:59:52] The next technique to use is firewalls.
[01:59:55] A firewall acts as a gatekeeper,
[01:59:57] filtering the malicious traffic from the
[02:00:00] other normal traffic. So, typically, you
### chunk 182 [02:00:00]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

e malicious traffic from the
[02:00:00] other normal traffic. So, typically, you[02:00:03] have it between your API and the
[02:00:05] incoming traffic. For example, if you
[02:00:07] use the AWS's web application firewall,
[02:00:11] this can block requests with unknown
[02:00:13] attack patterns such as suspicious SQL
[02:00:15] keywords or strange HTTP methods, which
[02:00:18] means it will block any suspicious
[02:00:20] requests from attackers, but it will
[02:00:22] allow others to bypass the request and
[02:00:25] reach to your API.
[02:00:27] Some APIs are also private and should
[02:00:29] only be accessed from specific networks.
[02:00:32] That's why we have also VPNs, which
[02:00:34] stands for virtual private networks. The
[02:00:37] APIs that are within the VPN network can
[02:00:40] only be accessed by someone who is also
### chunk 183 [02:00:40]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

re within the VPN network can
[02:00:40] only be accessed by someone who is also[02:00:43] within that same network, which Which
[02:00:45] that some APIs are public facing,
[02:00:47] meaning these APIs will allow any
[02:00:49] requests from the internet from your
[02:00:51] users. But this for example can be
[02:00:54] within the VPN network, which means if a
[02:00:57] user from web tries to reach your API,
[02:01:00] then this request will be blocked
[02:01:02] because the user is not within the same
[02:01:04] network. But on the other hand, if you
[02:01:06] have another user here, which is within
[02:01:09] the VPN network, they can make a request
[02:01:11] to these APIs and in this case they will
[02:01:14] bypass the checks and their will reach
[02:01:17] to your APIs.
[02:01:18] This is useful where you have internal
### chunk 184 [02:01:17]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

reach
[02:01:17] to your APIs.
[02:01:18] This is useful where you have internal[02:01:20] tools. Let's say you have internal admin
[02:01:22] dashboard and the API for this admin
[02:01:25] panel will only be reachable by
[02:01:27] employees connected to the company VPN.
[02:01:30] Next we have CSRF, which stands for
[02:01:32] cross-site request forgery. This tricks
[02:01:35] a logged-in user's browser into making
[02:01:38] unwanted requests to the API. Let's say
[02:01:41] you as a user are logged in into your
[02:01:43] bank system and your bank system uses
[02:01:46] cookies for authentication. If the bank
[02:01:49] system is not secure and they only use
[02:01:51] session cookies, another malicious site
[02:01:54] might use your cookie and submit a
[02:01:56] hidden transferring money request
[02:01:58] through your cookie. So to prevent such
### chunk 185 [02:01:58]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

en transferring money request
[02:01:58] through your cookie. So to prevent such[02:02:01] attacks, companies also use CSRF tokens
[02:02:03] in combination with session cookie. So
[02:02:06] the banking system will check if the
[02:02:08] session cookie is present, but it will
[02:02:10] also check if the CSRF token matches
[02:02:13] with the one that they have. And if it
[02:02:15] doesn't, then it will block this request
[02:02:17] from the other unknown source, while it
[02:02:20] will allow request from your behalf.
[02:02:23] And the last one we have is XSS or it's
[02:02:25] also called cross-site scripting. This
[02:02:28] lets attackers to inject scripts into
[02:02:30] web pages served to other users. For
[02:02:33] example, if you have a comment section
[02:02:36] and this comment gets submitted to your
[02:02:38] API, next your API will also store it in
### chunk 186 [02:02:38]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

mment gets submitted to your
[02:02:38] API, next your API will also store it in[02:02:41] a database. You can get normal requests
[02:02:44] like nice picture or something like
[02:02:46] that, and this will get to your API.
[02:02:48] Your API will store it in the database.
[02:02:50] So, everything is fine there. But, what
[02:02:53] if an attacker places a script in this
[02:02:55] comment section? And within this script,
[02:02:58] they can try to do many different
[02:03:00] things. For example, they can try to
[02:03:02] fetch the cookie for another user, or
[02:03:05] they can try to inject something into
[02:03:07] your database. And if you allow this,
[02:03:10] then it will reach to your server, and
[02:03:12] the information will be written into the
[02:03:14] database. Later, when the other users
[02:03:17] load these comments section on their
### chunk 187 [02:03:17]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

ase. Later, when the other users
[02:03:17] load these comments section on their[02:03:20] screen, they will get also the injected
[02:03:22] comment directly into their web page,
[02:03:25] and the browser will execute this
[02:03:27] malicious JavaScript code into the other
[02:03:29] users' browser. What you just went
[02:03:31] through were the first two sections of
[02:03:33] my system design mastery course, and
[02:03:36] this is just one piece in my mentorship
[02:03:38] program. If you want to go through the
[02:03:41] rest of these and actually master system
[02:03:43] design, not only at theory level, but to
[02:03:46] a point where you can design, build, and
[02:03:48] host full-stack systems end-to-end under
[02:03:50] my guidance, and get to senior and staff
[02:03:53] level by learning everything it takes to
### chunk 188 [02:03:53]
System Design Explained: APIs, Databases, Caching, CDNs, Load Balancing & Production Infra > Transcript

 and get to senior and staff
[02:03:53] level by learning everything it takes to[02:03:55] level up in your career, then there is a
[02:03:57] link in the description for you, which
[02:03:59] you can check out, apply, and see if you
[02:04:01] qualify for the program.
[02:04:03] Hope you liked the course, and see you
[02:04:05] in the next one.
