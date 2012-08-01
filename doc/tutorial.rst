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
from Excel or other programs.  Only two columns (ID number and name)
are needed, with no header line, e.g.::

  1,"Bob Smith"
  2,"Jane Doe"

You initialize the course database by running the following command::

  python /path/to/socraticqs/coursedb.py students.csv

This will create a sqlite3 database file ``course.db`` in the
current directory.

Configuring Socraticqs
----------------------

The config file is ``cp.conf``, and specifies things like the port
that the web server will run on (by default port 8000).  You can
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
  * ``image``: image response; the student answers by uploading an
    image.  **Not recommended**, as image files are huge and will
    slow your network to a crawl.  Not feasible for even for a medium
    sized class.

* question title

* question text

* text answer / explanation

For multiple choice questions, addition columns are required:

* the index of the correct choice, in standard Python zero-based
  indexing (i.e. zero is the first choice; 1 is the second choice, etc.).

* the remaining columns will be interpreted as the choices of
  the multiple choice question.

This format is generated automatically using my ReusableText tools,
but could be generated easily using Excel or many other programs
that can save CSV format.

Starting Socraticqs
-------------------

You start the Socraticqs server (in a directory containing a
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
  server shutdown.

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

Socraticqs saves all student responses in an sqlite3 database 
file (by default ``course.db``).  Currently some rudimentary
reporting method are available.  For example, you can see 
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
to a ReStructureText file ``myreport.rst``.

 
