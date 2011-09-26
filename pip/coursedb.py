import cherrypy
import os.path
import sqlite3
import csv
from datetime import datetime, date
from question import questionTypes
import random
import Queue

class BadUIDError(ValueError):
    pass

class BadUsernameError(ValueError):
    pass

class Student(object):
    def __init__(self, uid, fullname, username=None):
        self.uid = uid
        self.fullname = fullname
        self.username = username

class CourseDB(object):
    def __init__(self, questionFile=None, studentFile=None,
                 dbfile='course.db', createSchema=False, nmax=1000):
        self.dbfile = dbfile
        self.logins = set()
        codes = range(nmax)
        random.shuffle(codes) # short but random unique IDs for students
        self.idQueue = Queue.Queue() # thread-safe container
        for i in codes: # each student will get one ID from the container
            self.idQueue.put(i)
        if not os.path.exists(dbfile):
            createSchema = True
        conn = sqlite3.connect(dbfile)
        c = conn.cursor()
        if createSchema:
            c.execute('''create table students
            (uid integer primary key,
            fullname text,
            username text,
            date_added integer,
            added_by text)''')
            c.execute('''create table questions
            (id integer primary key,
            qtype text,
            title text,
            date_added integer)''')
            c.execute('''create table responses
            (id integer primary key,
            uid integer,
            question_id integer,
            cluster_id integer,
            is_correct integer,
            answer text,
            attach_path text,
            confidence integer,
            submit_time integer,
            reasons text,
            switched_id integer,
            confidence2 integer,
            final_id integer,
            final_conf integer,
            critique_id integer,
            criticisms text)''')
            conn.commit()
        if studentFile:
            self.load_student_file(studentFile, c=c, conn=conn)
        else:
            self.make_student_dict(c)
        if questionFile:
            self.load_question_file(questionFile, c=c, conn=conn)
        c.close()
        conn.close()

    def make_student_dict(self, c):
        'build dict from the student db'
        c.execute('select uid, fullname, username from students')
        d = {}
        users = {}
        for t in c.fetchall():
            student = Student(*t)
            student.code = self.idQueue.get() # get a unique random code
            d[student.uid] = student
            if student.username:
                users[student.username] = student
        self.students = d
        self.userdict = users

    def load_student_file(self, path, **kwargs):
        'read UID,fullname CSV file'
        self.save_csv_to_db(path, self.insert_students, self.make_student_dict,
                            **kwargs)

    def insert_students(self, users, c):
        for uid,fullname in users:
            c.execute('insert into students values (?,?,NULL,date(?),"admin")',
                      (uid, fullname, date.today().isoformat()))

    def save_csv_to_db(self, path, func, postfunc=None, c=None, conn=None):
        'generic csv reader, uses func to actually save the rows to db'
        ifile = open(path, 'Ub')
        try:
            rows = csv.reader(ifile)
            if not c: # need to open connection to the database
                conn = sqlite3.connect(self.dbfile)
                c = conn.cursor()
                doClose = True
            else:
                doClose = False
            try:
                func(rows, c)
                conn.commit()
                if postfunc:
                    postfunc(c)
            finally:
                if doClose: # need to close our connection
                    c.close()
                    conn.close()
        finally:
            ifile.close()

    def authenticate(self, uid, username):
        'validate a login'
        try:
            if self.userdict[username].uid == uid:
                return True
            else:
                raise BadUIDError('incorrect UID for ' + username)
        except KeyError:
            if uid in self.students:
                raise BadUsernameError('did you mistype your username?')
            raise BadUsernameError('unknown user ' + username)

    def login(self, uid, username):
        'add this student as an active login on this session'
        cherrypy.session['UID'] = uid
        cherrypy.session['username'] = username
        self.logins.add(uid)

    def logout(self, uid):
        cherrypy.lib.sessions.expire()
        self.logins.remove(uid)

    def add_student(self, uid, username, fullname, uid2):
        'add a login'
        if uid != uid2:
            raise BadUIDError('the UIDs do not match!')
        try:
            student = self.students[uid]
        except KeyError: # a new UID
            return self._new_student(uid, username, fullname)
        # add username to an existing UID
        if student.username:
            return 'You have already registered as user ' + student.username
        if username in self.userdict:
            raise BadUsernameError('Username %s is already taken.  Try again.'
                                   % username)
        student.username = username
        self.userdict[username] = student
        self._execute_and_commit('update students set username=? where uid=?',
                               (username, uid))
        return 'Saved username ' + username

    def _new_student(self, uid, username, fullname):
        if username in self.userdict:
            raise BadUsernameError('Username %s is already taken.  Try again.'
                                   % username)
        self._execute_and_commit('insert into students values (?,?,?,date(?),"user")',
                                 (uid, username, fullname,
                                  date.today().isoformat()))
        student = Student(uid, fullname, username)
        student.code = self.idQueue.get() # get a unique random code
        self.students[uid] = student
        self.userdict[username] = student
        return 'Added user ' + username

    def _execute_and_commit(self, sql, args):
        'execute a change to the db and commit it'
        conn = sqlite3.connect(self.dbfile)
        c = conn.cursor()
        try:
            c.execute(sql, args)
            conn.commit()
        finally:
            c.close()
            conn.close()

    def load_question_file(self, path, **kwargs):
        'read from CSV file to self.questions, and save to database'
        self.save_csv_to_db(path, self.insert_questions, **kwargs)

    def insert_questions(self, questions, c):
        l = []
        for t in questions:
            c.execute('insert into questions values (NULL,?,?,date(?))',
                      (t[0], t[1], date.today().isoformat()))
            klass = questionTypes[t[0]]
            if t[0] == 'mc':
                q = klass(t[1], t[2], t[3], t[4], t[5:]) # multiple choice answer
            else:
                q = klass(*t[1:])
            q.id = c.lastrowid
            q.courseDB = self
            l.append(q)
        self.questions = l

    def save_responses(self, question):
        'save all responses to this question to the database'
        def get_id(r, attr): # return None or the object's db id
            resp = getattr(r, attr, None)
            if resp:
                return resp.uid
        conn = sqlite3.connect(self.dbfile)
        c = conn.cursor()
        n = 0
        try:
            for r in question.responses.values(): # insert rows
                dt = datetime.fromtimestamp(r.timestamp)
                c.execute('''insert into responses values
                (NULL,?,?,?,?,?,?,?,datetime(?),?,?,?,?,?,?,?)''',
                          (r.uid, question.id, get_id(r, 'prototype'),
                           question.is_correct(r),
                           r.get_answer(), getattr(r, 'path', None),
                           r.confidence,
                           dt.isoformat().split('.')[0],
                           getattr(r, 'reasons', None),
                           get_id(r, 'response2'),
                           getattr(r, 'confidence2', None),
                           get_id(r, 'finalVote'),
                           getattr(r, 'finalConfidence', None),
                           get_id(r, 'critiqueTarget'),
                           getattr(r, 'criticisms', None)))
                r.id = c.lastrowid # record its primary key
            conn.commit()
            n = len(question.responses)
        finally:
            c.close()
            conn.close()
        return n # number of saved responses

