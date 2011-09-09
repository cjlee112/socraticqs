import cherrypy
import webui
import thread
import os.path
import sqlite3
import csv
import login

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
    def __init__(self, dbfile='course.db', createSchema=False):
        self.dbfile = dbfile
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
            conn.commit()
        self.make_student_dict(c)
        c.close()
        conn.close()

    def make_student_dict(self, c):
        'build dict from the student db'
        c.execute('select uid, fullname, username from students')
        d = {}
        users = {}
        for t in c.fetchall():
            student = Student(*t)
            d[student.uid] = student
            if student.username:
                users[student.username] = student
        self.students = d
        self.userdict = users

    def load_student_file(self, path):
        'read UID,fullname CSV file'
        ifile = open(path, 'Ub')
        try:
            users = csv.reader(ifile)
            conn = sqlite3.connect(self.dbfile)
            c = conn.cursor()
            try:
                for uid,fullname in users:
                    c.execute('insert into students values (?,?,NULL,date("now"),"admin")',
                              (uid, fullname))
                conn.commit()
                self.make_student_dict(c)
            finally:
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
        self._execute_and_commit('insert into students values (?,?,?,date("now"),"user")',
                               (uid, username, fullname))
        student = Student(uid, fullname, username)
        self.students[uid] = student
        self.userdict[username] = student
        return 'Added user ' + username

    def _execute_and_commit(self, sql, args):
        'execute a change to the db for commiting it later'
        conn = sqlite3.connect(self.dbfile)
        c = conn.cursor()
        try:
            c.execute(sql, args)
            conn.commit()
        finally:
            c.close()
            conn.close()


class QuestionBase(object):
    def __init__(self, title, text, *args, **kwargs):
        doc = webui.Document(title)
        self.doc = doc
        doc.add_text(text)
        doc.append(self.build_form(*args, **kwargs))
        self.responses = {}

    def __str__(self):
        return str(self.doc)

class QuestionChoice(QuestionBase):
    def build_form(self, choices):
        'ask the user to choose and option and enter a short text reason'
        self.choices = choices
        form = webui.Form('answer')
        form.append(webui.Selection('choice', list(enumerate(choices))))
        form.append('<br>\n')
        form.append(webui.Data('Explain:'))
        form.append(webui.Input('reason', size=50))
        form.append('<br>\n')
        return form

    def answer(self, choice=None, reason=None):
        uid = cherrypy.session['UID']
        if not choice or not reason:
            pass
        self.responses[uid] = (choice, reason)
        return 'Thanks for answering! <A HREF="/">Continue</A>'
    answer.exposed = True


class QuestionUpload(QuestionBase):
    def build_form(stem='q', instructions='''(write your answer on a sheet of paper, take a picture,
        and upload the picture using the button below).<br>\n'''):
        'ask the user to upload an image file'
        self.stem = stem
        self.doc.append(webui.Data(instructions))
        form = webui.Form('answer')
        form.append(webui.Upload('image'))
        form.append('<br>\n')
        return form

    def answer(self, image=None):
        'receive uploaded image file from user'
        uid = cherrypy.session['UID']
        fname = self.stem + str(len(self.responses)) + '_' + image.filename
        ifile = open(fname, 'w')
        ifile.write(image.file.read())
        ifile.close()
        self.responses[uid] = (fname, image.content_type)
        return 'Thanks for answering! <A HREF="/">Continue</A>'
    answer.exposed = True

def redirect(path='/', delay=0):
    s = '<HTML><HEAD>\n'
    s += '<meta http-equiv="Refresh" content="%d; url=%s">\n' % (delay, path)
    s += '</HEAD></HTML>\n'
    return s

class PipRoot(object):
    _cp_config = {'tools.sessions.on': True}

    def __init__(self, enableMathJax=False, registerAll=False, **kwargs):
        self.courseDB = CourseDB(**kwargs)
        self._registerHTML = login.register_form()
        if registerAll:
            self._loginHTML = self._registerHTML
        else:
            self._loginHTML = login.login_form()
        self._reloadHTML = redirect()
        self.enableMathJax = enableMathJax
    
    def serve_question(self, question):
        self._question = question
        if self.enableMathJax:
            question.doc.head.append('<script type="text/javascript" src="/MathJax/MathJax.js?config=TeX-AMS-MML_HTMLorMML"></script>\n')
        self._questionHTML = str(question)
        self.answer = question.answer
        
    def index(self):
        try:
            uid = cherrypy.session['UID']
        except KeyError:
            return self._loginHTML
            
        try:
            return self._questionHTML
        except AttributeError:
            return 'No question has been set!'
    index.exposed = True

    def start(self):
        self.threadID = thread.start_new_thread(self.serve_forever, ())

    def serve_forever(self):
        cherrypy.quickstart(self, '/', 'cp.conf')

    def login(self, username, uid):
        try:
            uid = int(uid)
        except ValueError:
            return 'Your UID must be an integer! <A HREF="/">Continue</A>'
        try:
            self.courseDB.authenticate(uid, username)
        except ValueError, e:
            return str(e) + ' <A HREF="/">Continue</A>'
        cherrypy.session['UID'] = uid
        cherrypy.session['username'] = username
        return self._reloadHTML
    login.exposed = True

    def register_form(self):
        return self._registerHTML
    register_form.exposed = True

    def register(self, username, fullname, uid, uid2):
        try:
            uid = int(uid)
            uid2 = int(uid2)
        except ValueError:
            return 'Your UID must be an integer! <A HREF="/register_form">Continue</A>'
        if not username:
            return 'You must supply a username! <A HREF="/register_form">Continue</A>'
        try:
            msg = self.courseDB.add_student(uid, username, fullname, uid2)
        except ValueError, e:
            return str(e) + ' <A HREF="/register_form">Continue</A>'
        cherrypy.session['UID'] = uid
        cherrypy.session['username'] = username
        return msg + '. <A HREF="/">Continue</A>'
    register.exposed = True
        
def test(title='Monty Hall',
         text=r'''The probability of winning by switching your choice is:
         $$x = {-b \pm \sqrt{b^2-4ac} \over 2a}.$$''',
         choices=('1/3','1/2','2/3', 'Impossible to say')):
    q = QuestionChoice(title, text, choices)
    s = PipRoot(True)
    s.serve_question(q)
    s.start()
    return s
