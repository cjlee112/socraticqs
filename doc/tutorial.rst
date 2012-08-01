################
Using Socraticqs
################

Teaching with Socraticqs
------------------------

You use Socraticqs rather like a set of slides that you can
step through in any order you want, showing or skipping whatever
you want.  The only difference is that you should tell the
students what to click on when you want them to do something:

* when you start a new question, tell them to click the START
  link on the navigation bar that is always at the bottom of any
  Socraticqs page.
* if you want them to report whether peer discussion changed
  what they think is the right answer, tell them to click
  the DISCUSS link.  Note that this is *optional*; it's up
  to you based on whether you think it's worth the time;
  I usually skip this.
* when you want to present the right answer, you can tell them
  to click the ASSESS link to enter a self-evalation of whether
  their answer matched or differed from the right answer.
  Note that this is *optional*; it's up
  to you based on whether you think it's worth the time;
  I almost always do this, as I want to see how the students
  evaluate their own answers.

You can of course use Socraticqs in any way you wish.  After
experimenting with various procedures, I've settled into a
fairly "minimal" question cycle:

* introduce and explain the question; make sure they understand
  what's being asked.
* Click Socraticqs Go button to start its timer and tell the
  students to think about the question for one minute.
* After about a minute I tell them to start entering whatever
  brief answer they've come up with.
* After another minute to enter their answers, I tell them
  to discuss their answer with their partner whenever they're
  both ready.
* After a couple minutes for them to each present their answer to
  each other (I tell them one minute each), I show them the answer
  and explain it.
* I then ask them to self-assess, and give them a minute or two
  to do that.

Note that it's usually not practical to wait for *everyone* to
finish every stage before proceeding to the next one.  Instead
I simply want to see that most of the students have entered an
answer.  Socraticqs is designed to allow students to continue
answering one stage after you've moved on to another stage.
The main thing is that once you assign a new question, when
a student clicks the START link they'll get your new question.

I usually take about 10 minutes per question (for the whole cycle).
Clearly you must choose your questions carefully and to the point;
you only get to ask a few questions per class!  I prefer a two-hour
class format, which gives me enough time to cover a topic and
work through enough concept tests.  I have tried two different
approaches:

* minimal lecture, mostly concept tests: Eric Mazur recommends
  that students be *required* to do assigned reading that 
  prepares them for the in-class questions.  This has to be
  enforced by frequent pop quizzes.  The reading should be
  brief and concise, focused on introducing the definitions
  and concepts.  (The quizzes should merely assess whether
  they've done the reading and know basic definitions, *not*
  whether they truly understand the concepts).  The class time
  then builds understanding through conceptual questions.

  In my experience, the difficulty with this approach is that it's
  too different from what students are used to.  Some of them
  will resent the change simply because it isn't what
  they expected.  I also find that the extra mechanics
  involved (pop quizzes) waste time for little benefit.

* balance of lecture and concept tests: lecture about half 
  of the class time, and pose concept tests the rest of the time.
  You can of course still assign reading, but it becomes less
  critical and there's no need for reading quizzes.

  Students seem to find this an appealing mix of what they're
  used to (lecture) plus something new (concept tests).  They
  still feel the comfort of the familiar format, and in that mood
  seem to welcome concept tests as "good exercise" that wakes
  them up and adds to their understanding.  I find this
  approach to be a "happy medium".

  You could either intersperse lecture and concept tests, topic
  by topic, or you could lecture for an hour and then have
  an hour of concept tests.


Coordination with Slides
........................

In principle, you could just use Socraticqs Instructor interface
to present the questions and answers to the students (i.e. project
your web browser showing the Instructor interface, for the
students to see).  However, I prefer to show slides of
the questions and answers on an external monitor (projected
for the students to see), while I keep the Instructor interface
on my laptop screen, not visible to the students.  (My 
ReusableText tools generate both PDF slides and a Socraticqs question
file automatically from the same question text).

Course Setup
------------

You initialize a Socraticqs course database by giving it a list
of students in CSV format.  This list actually could consist of
just one student, as Socraticqs allows students to register in-class
by simply giving their full name and student ID number.
The students file is read from CSV format, which can be exported
from Excel or other programs.  Only two columns (student ID number and name)
are needed, with no header line, e.g.::

  1082376,"Bob Smith"
  2997389,"Jane Doe"

You initialize the course database by running the following command::

  python /path/to/socraticqs/coursedb.py students.csv

This will create a sqlite3 database file ``course.db`` in the
current directory.

Configuring Socraticqs
----------------------

The config file is ``cp.conf``, and specifies things like the port
that the web server will run on (by default, port 8000).  You can
change the settings if you wish.

Socraticqs Question File Format
-------------------------------

You start a Socraticqs session by giving it a list of questions
in CSV format, consisting of the following columns (again with no 
header line):

* question type

  * ``mc``: multiple choice; the student chooses one of several answers.
  * ``text``: text response; the student answers by typing text and / or 
    equations.
  * ``image``: image response; the student answers by writing and / or
    drawing on a piece of paper, then uploading an
    image of it from their laptop's webcam or smartphone camera.
    **Not recommended**, as image files are huge (especially from
    modern smartphone cameras) and will
    slow your network to a crawl.  Not feasible for even a medium
    sized class.

* question title

* question text

* text answer / explanation

For multiple choice questions, additional columns are required:

* the index of the correct choice, in standard Python zero-based
  indexing (i.e. zero is the first choice; 1 is the second choice, etc.).

* the remaining columns will be interpreted as the texts of
  each of the answer choices of the multiple choice question.

This format is generated automatically using my ReusableText tools,
but could be generated easily using Excel or many other programs
that can save CSV format.

MathJax Equation Support
........................

If you download the `MathJax <http://www.mathjax.org/>`_ 
package and install it (or link it)
as ``/path/to/socraticqs/static/mathjax``, Socraticqs will support
the rendering of LaTeX equations in the usual MathJax way, i.e.::

  this is an inline equation \(y=x^2\)

  Here is an equation on its own line:

  $$a^2+b^2=c^2$$

Note that this equation support works both in question text
and in student response text, i.e. when a student response
is displayed on a Socraticqs page, the equation will be 
rendered by MathJax.

Note that if you use equations in Socraticqs, you should
recommend that students use `Firefox <http://www.mozilla.org/>`_ ,
because this should use Firefox's native MathML support, 
hopefully improving performance
(by avoiding the need to send font data to the students'
browsers).

Starting Socraticqs
-------------------

You start the Socraticqs server (in a directory containing your
``course.db`` course database) as follows::

  python /path/to/socraticqs/web.py myquestions.csv


The Admin (Instructor) Interface
------------------------------------------

Currently, Socraticqs is configured to only allow admin access
from web browsers on the same computer where the server is running.
E.g. if you are using the default port setting of 8000, then
you would point your web browser at 

http://localhost:8000/admin

The admin interface is simple:

* START page: shows the list of questions.  Click a question to
  start the students on that question.
* MONITOR page: shows the question, 
  how many students have submitted an answer
  to the current question, and (if desired) their answers.
  Automatically updates every 15 seconds.
* ASSESS page: shows the answer, how many students have submitted
  a self-evaluation, and (if desired) their self-evaluations.
  Automatically updates every 15 seconds.
* SAVE: saves the latest student response data to the database.
  It is safe to click this as often as you like if you're paranoid,
  but strictly speaking there is no need to save data until
  the end of class.
* SHUTDOWN: saves data and shuts down the server.  Currently
  you will just get a warning from your web browser that the 
  server has gone away; we will improve this.

These options are always available by clicking on the navigation
bar at the bottom of any page.


The Student Interface
---------------------

Tell the students the URL of the server; on a private network this
will consist of your IP address and port number, e.g.

http://192.168.0.2:8000/

For convenience, you should configure your wifi access point to
always assign the same IP address to your computer (server).  Then
you can tell the students to just bookmark the URL the first day,
so they can access it very easily thereafter.

Registration and Login
......................

To use Socraticqs, each student must *register* by creating a username.
They select a username, and enter their full name and student ID number.

Thereafter, they login to Socraticqs with their username and student ID
number.

The Socraticqs Navigation Bar
.............................

Just as in the Instructor interface, there is a *navigation bar*
at the bottom of every page of the student interface.
It lets students navigate to several possible pages
(typically, when the instructor tells them to):

* START: displays the current question assigned by the instructor,
  for the student to answer.
* DISCUSS: enables the student to report whether discussion with
  their partner changed their answer.
* ASSESS: lets the student report whether their answer matched or
  differed from the correct solution.

Database and Reporting
----------------------

Note that you must explicitly save student responses to
its database file; Socraticqs does so whenever you click SAVE or SHUTDOWN.
Above all, do not simply kill the server (e.g. by typing control-C)
without saving data first!  For maximal speed, Socraticqs
keeps all data in memory and does not use database queries
when processing student responses.  Thus you must save the
data before the Socraticqs server process halts, or you will
lose the student response data from that session (responses
previously stored in the database file will still be there, of course).

Socraticqs saves all student responses in an sqlite3 database 
file (by default ``course.db``).  Currently some rudimentary
reporting methods are available.  For example, you can see 
a list of all questions in the database using the ``sqlite3``
tool (installed by default on Mac OS X)::

  $ sqlite3 course.db
  SQLite version 3.6.12
  Enter ".help" for instructions
  Enter SQL statements terminated with a ";"
  sqlite> select * from questions;
  1|text|ortholog vs. paralog evolution|2012-07-31
  2|text|repetitive elements and assembly|2012-07-31
  3|text|Solexa vs. PCR?|2012-07-31
  4|text|solexa sequencing limits|2012-07-31

You can then use Socraticqs' ``write_report.py`` script to
generate a report of the student responses for a specified list
of questions::

  python /path/to/socraticqs/write_report.py myreport.rst 1,2,3,4

makes it write a report of the responses to questions 1, 2, 3, and 4
to a `ReStructuredText <http://sphinx.pocoo.org/rest.html>`_ 
file ``myreport.rst``.

 
Classroom Wi-Fi Configurations
------------------------------

First, note that Socraticqs **does not** need an Internet
connection, either for the server (e.g. on the instructor's laptop)
or for the students.  The only need for wi-fi is as a way for
the students' laptops and smartphones to connect to the
Socraticqs server (most likely running on the instructor's laptop).

If your classroom has robust wi-fi, then all you need to do is
connect your laptop (on which you will run the Socraticqs server)
to the wi-fi, note its IP address, and start Socraticqs.
Then tell your students the URL to point their web browsers
at (based on your IP address; see details above).  At that point
they should all be able to log in.

On the other hand, if your classroom lacks usable wi-fi, you
have several choices:

* use a cheap wi-fi router, either with or without plugging it into
  an Internet connection.  For best performance, you can plug
  your laptop (that will run the Socraticqs server) directly into
  the router using an ethernet cable.  You then tell the
  students how to connect their laptops to the wi-fi router,
  and the URL to point their web browser at the Socraticqs
  server (based on your IP address; see details above).

  This is a robust, scalable solution,
  and has worked flawlessly for me in the two courses where I've
  used Socraticqs (with up to 60 students).

* if you're running Socraticqs on a MacBook, you can choose
  "Create Network..." under the wi-fi menu to create an ad hoc
  network.  You then tell the students the network name you
  chose, and they connect their laptops to it.  You tell them
  the URL for the Socraticqs
  server (based on your IP address; see details above).

  I haven't tested this, but presumably it might have lower
  performance and not be usable for larger numbers of students.

Note: I generally do not start the Socraticqs server until *after*
my laptop has acquired the IP address that it will use throughout
the session (e.g. from the wi-fi router you attach it to).  I'm not
sure if this precaution is needed.

Why's it called "Socraticqs"?
-----------------------------

The full name is the "Socraticqs In-Class Question System",
Socraticqs for short.  
Pronounce it like "socratics" (the Q is silent!).  
This was the best compromise I could think of between
several desires:

* I wanted to tip the hat to the Socratic Method, the one method for
  "teaching with questions" that people have heard of.
* I wanted to call this an "In-Class Question System" to distinguish exactly
  what it's for (and to differentiate it from existing packages
  like Moodle).
* I didn't want this to sound like a package
  for Greek, Classics or philosophy.
* I wanted the name to obviously be computer software,
  but baulked at ugly acronyms like "SocratICQS".
* I figured people will ignore the Q and pronounce Socraticqs
  just like "socratics"; I wanted the name to be easy to pronounce
  and to sound like a regular word.

