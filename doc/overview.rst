
################################################################
The What, Why and How of the Socraticqs In Class Question System
################################################################

What is Socraticqs?
-------------------

Socraticqs is an open-source In-Class Question System designed
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

Who might want to use it and why?
---------------------------------

* you want to be able to use equations (latex) in both your
  questions and the students' answers, and have everything
  display nicely on the students' laptops and smartphones.

* you already use clickers or some other method to collect
  student answers in class, but you'd like to use something
  less expensive (free!), more convenient (use students'
  laptops and smartphones instead of clickers), or more
  powerful (e.g. freeform response, equations etc.).

* you want to ask students questions in class and collect
  their responses, but want to be able to easily do it yourself,
  without requiring a special server or IT support.

* you want to use Peer Instruction in your class.

* you want to use Concept Testing (the "Socratic Method")
  in your class.

* you want to be able to customize or extend what kinds
  of question or answer formats are possible, which is
  straightforward with this simple open-source Python tool.


Installation
------------

Socraticqs requires

* `Python <http://python.org>`_
* `CherryPy <http://cherrypy.org>`_
* If you want equation display support, you also need 
  `MathJax <http://www.mathjax.org/>`_

You can download the latest release of Socraticqs from
https://github.com/cjlee112/socraticqs/tags
(or obtain the very latest development version from the 
GitHub repository there).  Then untar / unzip the downloaded
package in the usual way, e.g.::

  tar xzf socraticqs-v0.3.tar.gz

You have two options for how to install the package:

* option 1: run the standard Python package installation mechanism, e.g.::

    cd socraticqs
    sudo python setup.py install

  (leave out the ``sudo`` part of the command if you are installing
  to a location that you have write-privileges for).

  This option has one advantage: it will install ``CherryPy`` for
  you if you are missing it.

* option 2: simply run socraticqs commands directly from the
  source code directory, using commands like::

    python /path/to/socraticqs/web.py myquestions.csv


