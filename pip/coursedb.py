import cherrypy
import os.path
import sqlite3
import csv
from datetime import datetime, date
from question import questionTypes
import random
import Queue
import re
import codecs

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
                                 (uid, fullname, username,
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
                q = klass(c.lastrowid, t[1], t[2], t[3], t[4], t[5:]) # multiple choice answer
            else:
                q = klass(c.lastrowid, *t[1:])
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

    def write_report(self, rstfile, qlist, title='Report', **kwargs):
        ifile = codecs.open(rstfile, 'w', 'utf-8')
        print >>ifile, ('#' * len(title)) + '\n' + title + '\n' + ('#' * len(title)) + '\n'
        conn = sqlite3.connect(self.dbfile)
        c = conn.cursor()
        try:
            for qid in qlist:
                c.execute('select qtype, title from questions where id=?',
                          (qid,))
                qtype, qtitle = c.fetchall()[0]
                if qtype == 'mc':
                    self.question_report(ifile, qid, c, qtitle, 'answer',
                                         **kwargs)
                else:
                    self.question_report(ifile, qid, c, qtitle, **kwargs)
        finally:
            c.close()
            conn.close()
            ifile.close()
    def question_report(self, ifile, qid, c, title, orderBy='cluster_id',
                        showReasons=False):
        letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        print >>ifile, '\n' + title + '\n' + ('-' * len(title)) + '\n\n'
        currentID = None
        i = 0
        d = {}
        critiques = {}
        is_correct = {}
        answer = {}
        c.execute('select uid, cluster_id, is_correct, answer, reasons, switched_id, final_id, critique_id, criticisms from responses where question_id=? order by %s'
                  % orderBy, (qid,))
        order = []
        uncategorized = []
        for t in c.fetchall():
            if t[1] is None: # not categorized so not usable
                uncategorized.append(t)
                continue
            try:
                d[t[1]].append(t)
            except KeyError:
                order.append(t[1])
                d[t[1]] = [t]
                try:
                    if int(t[2]):
                        is_correct[t[1]] = 'Correct'
                    else:
                        is_correct[t[1]] = 'Wrong'
                except TypeError:
                    is_correct[t[1]] = 'Uncategorized'
            if t[0] == t[1]: # prototype
                answer[t[1]] = t[3]
            if t[-2] == t[0]: # self-critique
                critiqueID = t[1]
            else:
                critiqueID = t[-2]
            if t[-1]:
                try:
                    critiques[critiqueID].append(t[-1])
                except KeyError:
                    critiques[critiqueID] = [t[-1]]
        for cluster_id in order:
            rows = d[cluster_id]
            try:
                i = int(answer[cluster_id]) # only valid if multiple choice
            except KeyError: # no prototype found?  Use the first answer found
                l = [(len(t[3]),t[3]) for t in rows]
                l.sort() # find the longest answer for this category
                a = simple_rst(l[-1][1]) # text response
            except ValueError:
                a = simple_rst(answer[cluster_id]) # text response
            else:
                a = None
            s = 'Answer ' + letters[i] + ' (%s, %d people)' \
                % (is_correct[cluster_id], len(rows))
            i += 1
            print >>ifile, '\n' + s + '\n' + ('.' * len(s))
            if a: # print text response answer
                print >>ifile, '\n' + a
            if showReasons and rows:
                s = 'Reasons Given for this Answer'
                print >>ifile, '\n' + s + '\n' + ('+' * len(s)) + '\n'
                for t in rows:
                    if t[4]:
                        print >>ifile, '* ' + simple_rst(t[4], '\n  ')
            try:
                l = critiques[cluster_id]
            except KeyError:
                pass
            else:
                s = 'Critiques of this Answer'
                print >>ifile, '\n' + s + '\n' + ('+' * len(s)) + '\n'
                for criticism in l:
                    print >>ifile, '* ' + simple_rst(criticism, '\n  ')
        if uncategorized:
            s = 'Uncategorized Answers (%d people)' % len(uncategorized)
            print >>ifile, '\n' + s + '\n' + ('.' * len(s)) + '\n'
            uncategorized.sort(lambda t,u:cmp(t[4],u[4]))
            for t in uncategorized:
                s = t[3] + '.  '
                if t[4]:
                    s += '(' + t[4] + ').  '
                if t[-1]:
                    s += '**Difference:** ' + t[-1]
                print >>ifile, '* ' + simple_rst(s, '\n  ')


def simple_rst(s, lineStart='\n'):
    s = ' '.join(s.split('\r')) # get rid of non-standard carriage returns
    s = lineStart.join(s.split('\n')) # apply indenting
    s = re.sub('----+', '', s) # get rid of headings that will crash ReST
    s = re.sub(r'\$\$([\w^\\{}().]+)\$\$', r':math:`\1`', s) # treat as inline
    s = re.sub(r'\$\$([^$]+)\$\$\s*', '\n%s.. math:: \\1\n%s'
               % (lineStart, lineStart), s) # treat as displaymath
    return s
