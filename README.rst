
What is Socraticqs?
-------------------

`Socraticqs <http://people.mbi.ucla.edu/leec/docs/socraticqs/>`_
is an open-source In-Class Question System designed
for teaching by asking questions that
students answer in-class using their laptops or smartphones.
Concretely:

* it is a lightweight web server written in Python
  (usually run on the instructor's laptop)
  that students point their web browsers at, giving them an
  easy interface for answering the questions you assign.
* it also gives the instructor an easy web interface for
  walking the students through questions one step at a time.
* it captures all student responses in a database (sqlite3)
  for generating reports and whatever data analysis you want.

It differs from existing "e-learning" packages such as 
`Moodle <http://moodle.org>`_ in that

* it's designed to be used *in-class* to ask all the students
  to answer a question, and optionally discuss their answers
  and self-assess.  In class, time and simplicity are of the essence, 
  and keeping everybody in sync is key.

* it's designed to be fast, lightweight and simple, for use in class,
  typically running the Socraticqs server on the instructor's laptop.

* it supports a *concept testing* methodology.  That is,
  each question should probe understanding of a single concept
  in a way that requires thought rather than mechanics.
  Moreover, by allowing freeform response (students type short
  text or equation answers) rather than just multiple choice,
  it reveals the specific conceptual errors that students are
  making.

* it supports
  `Peer Instruction <http://mazur.harvard.edu/research/detailspage.php?ed=1&rowid=8>`_,
  in which students are paired
  (with the person sitting next to them in class) to present
  their answers to each other and see whether they find each
  other's arguments convincing.

* it gives the instructor total control in real time over exactly
  what questions or steps to do, speed up, or skip altogether.
  You choose a question to start by just clicking on it;
  you end it whenever you want; you can have the students do
  all the steps, or just one, however you decide at that moment.

