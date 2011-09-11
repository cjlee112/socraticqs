import cherrypy
import webui
import thread
import os.path
import sqlite3
import csv
import login
import time

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

letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'


class Response(object):
    'subclass this to supply different storage and representation methods'
    def __init__(self, uid, question, confidence, *args, **kwargs):
        self.uid = uid
        self.question = question
        self.timestamp = time.time()
        self.confidence = confidence
        self.save_data(*args, **kwargs)

    def save_data(self, **kwargs):
        for attr, val in kwargs.items():
            setattr(self, attr, val)

class MultiChoiceResponse(Response):
    def save_data(self, choice):
        self.choice = int(choice)
    def __str__(self):
        return '<B>%s</B>. %s<br>\n' % (letters[self.choice],
                                       self.question.choices[self.choice])
    def __cmp__(self, other):
        return cmp(self.choice, other.choice)
    def __hash__(self):
        return hash(self.choice)

class ClusteredResponse(Response):
    'a pair matches if they have the same prototype'
    def __cmp__(self, other):
        return cmp(id(self.prototype), id(other.prototype))
    def __hash__(self):
        try:
            return id(self.prototype)
        except AttributeError:
            return id(self)

class TextResponse(ClusteredResponse):
    def save_data(self, text):
        self.text = text
    def __str__(self):
        return self.text + '<br><hr>\n'

class ImageResponse(ClusteredResponse):
    def save_data(self, stem, image):
        self.fname = stem + '_' + image.filename
        ifile = open(self.fname, 'w')
        ifile.write(image.file.read())
        ifile.close()

class QuestionBase(object):
    def __init__(self, title, text, *args, **kwargs):
        doc = webui.Document(title)
        self.doc = doc
        doc.add_text(text)
        doc.append(self.build_form(*args, **kwargs))
        self.responses = {}
        self.categories = {}
        self.unclustered = set()

    def __str__(self):
        return str(self.doc)

    def reconsider(self, reasons, status, confidence, partner):
        uid = cherrypy.session['UID']
        response = self.responses[uid]
        if status == 'switched':
            try:
                partnerUID = self.courseDB.userdict[partner].uid
            except KeyError:
                return """Sorry, the username you entered for your partner
                does not exist.  Please re-enter it!
                <A HREF='/reconsider_form'>Continue</A>."""
            response.response2 = self.responses[partnerUID]
        response.reasons = reasons
        response.confidence2 = confidence
        return 'Thanks! <A HREF="/">Continue</A>.'
    reconsider.exposed = True

    def prototype_form(self, offset=0, maxview=10,
                       title='Categorize Responses'):
        if not self.unclustered:
            return self.cluster_report()
        doc = webui.Document(title)
        if self.categories: # not empty
            doc.add_text('%d Categories' % len(self.categories), 'h1')
            for r in self.categories:
                doc.add_text(str(r))
        doc.add_text('%d Uncategorized Responses' % len(self.unclustered), 'h1')
        l = list(self.unclustered)[offset:]
        if maxview and len(l) > maxview:
            l = l[:maxview]
        form = webui.Form('add_prototypes')
        for r in l:
            form.append(webui.RadioSelection('resp_' + str(r.uid),
                                             (('add', str(r)),)))
        doc.append(form)
        return str(doc)
    prototype_form.exposed = True
    def cluster_report(self):
        s = '<h1>Done</h1>%d responses in %d categories:' \
            % (len(self.responses), len(self.categories))
        return s

    def add_prototypes(self, **kwargs):
        for k,v in kwargs.items():
            if v == 'add':
                uid = int(k.split('_')[1])
                response = self.responses[uid]
                self.set_prototype(response)
        l = list(self.categories)
        l.sort()
        self.categoriesSorted = l
        self._clusterFormHTML = self.build_cluster_form()
    add_prototypes.exposed = True

    def set_prototype(self, response, category=None):
        if category is None: # response is prototype for its own category
            category = response
            self.categories[category] = [category]
        else:
            self.categories[category].append(response)
        response.prototype = category
        self.unclustered.remove(response)

    def cluster_form(self):
        uid = cherrypy.session['UID']
        response = self.responses[uid]
        if response in self.categories:
            return '''Your answer already matches a category.
            <A HREF="/">Continue</A>'''
        return self._clusterFormHTML
    cluster_form.exposed = True

    def build_cluster_form(self, title='Cluster Your Answer'):
        doc = webui.Document(title)
        doc.add_text('''Either choose the answer that basically matches
        your original answer, or choose <B>None of the Above</B><br>
        ''')
        form = webui.Form('cluster')
        l = []
        for i,r in enumerate(self.categoriesSorted):
            l.append((i, str(r)))
        l.append(('none', 'None of the above'))
        form.append(webui.RadioSelection('match', l))
        form.append('<br>\n')
        doc.append(form)
        return str(doc)

    def cluster(self, match):
        uid = cherrypy.session['UID']
        if match == 'none':
            return '''OK.  Hopefully we can cluster your answer in the next
            round.  <A HREF="/">Continue</A>.'''
        response = self.responses[uid]
        category = self.categoriesSorted[int(match)]
        self.set_prototype(response, category)
        return 'Thanks! <A HREF="/">Continue</A>.'
    cluster.exposed = True

    def build_vote_form(self, form=None, title='Vote for the best answer',
                        text='Which of the following answers do you think is correct?<br>\n'):
        doc = webui.Document(title)
        doc.add_text(text)
        if form is None:
            form = self.get_choice_form()
        doc.append(form)
        return str(doc)
    def get_choice_form(self, action='vote'):
        form = webui.Form(action)
        l = []
        for i,r in enumerate(self.categoriesSorted):
            l.append((i, str(r)))
        form.append(webui.RadioSelection('choice', l))
        form.append('<br>\n')
    def build_critique_form(self):
        form = self.get_choice_form('critique')
        form.append('<br>\nBriefly state what you think is wrong with this answer:<br>\n')
        form.append(webui.Textarea('criticisms'))
        form.append('<br>\n')
        return self.build_vote_form(form, 'Choose an answer to critique',
                                    'Choose one of the following answers to critique:<br>\n')

    def init_vote(self, title='Critique your original answer',
                  text='Briefly state what you think was wrong with your original answer:<br>\n',
                  action='self_critique'):
        self._voteHTML = self.build_vote_form()
        self._critiqueHTML = self.build_critique_form()
        doc = webui.Document(title)
        doc.add_text(text)
        form = webui.Form(action)
        form.append(webui.Textarea('criticisms'))
        form.append('<br>\n')
        doc.append(form)
        self._selfCritiqueHTML = str(doc)
        
    def vote(self, choice):
        uid = cherrypy.session['UID']
        response = self.responses[uid]
        category = self.categoriesSorted[int(choice)]
        response.finalVote = category
        if category != response:
            return self._selfCritiqueHTML
        else:
            return self._critiqueHTML
    vote.exposed = True

    def critique(self, criticisms, choice):
        category = self.categoriesSorted[int(choice)]
        self.save_critique(criticisms, category)
    critique.exposed = True
    
    def self_critique(self, criticisms):
        self.save_critique(criticisms)
    self_critique.exposed = True
    
    def save_critique(self, criticisms, category=None):
        uid = cherrypy.session['UID']
        response = self.responses[uid]
        if category is None: # treat this as a self-critique
            category = response
        response.critiqueTarget = category
        response.criticisms = criticisms
        return 'Thanks! <A HREF="/">Continue</A>'



class QuestionChoice(QuestionBase):
    def build_form(self, choices):
        'ask the user to choose an option and enter a short text reason'
        self.choices = choices
        form = webui.Form('answer')
        l = []
        for i,s in enumerate(choices):
            l.append((i, '<B>%s</B>. %s' % (letters[i], s)))
        form.append(webui.RadioSelection('choice', l))
        add_confidence_choice(form)
        form.append('<br>\n')
        ## form.append(webui.Data('Explain:'))
        ## form.append(webui.Input('reason', size=50))
        ## form.append('<br>\n')
        return form

    def answer(self, choice, confidence):
        uid = cherrypy.session['UID']
        response = MultiChoiceResponse(uid, self, confidence, choice)
        try: # append to its matching category
            self.categories[response].append(response)
        except KeyError: # add this as a new category
            self.categories[response] = [response]
        self.responses[uid] = response
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
        add_confidence_choice(form)
        form.append('<br>\n')
        return form

    def answer(self, image, confidence):
        'receive uploaded image file from user'
        uid = cherrypy.session['UID']
        response = ImageResponse(uid, self, confidence,
                                 self.stem + str(len(self.responses)),
                                 image)
        self.unclustered.add(response) # initially not categorized
        self.responses[uid] = response
        return 'Thanks for answering! <A HREF="/">Continue</A>'
    answer.exposed = True

def add_confidence_choice(form, levels=('Just guessing', 'Not quite sure',
                                        'Pretty sure')):
    form.append('<br>\nHow confident are you in your answer?<br>\n')
    form.append(webui.RadioSelection('confidence', list(enumerate(levels))))
    

def redirect(path='/', delay=0):
    s = '<HTML><HEAD>\n'
    s += '<meta http-equiv="Refresh" content="%d; url=%s">\n' % (delay, path)
    s += '</HEAD></HTML>\n'
    return s

def build_reconsider_form(title='Reconsidering your answer'):
    doc = webui.Document(title)
    doc.add_text('''Briefly state the key points that you used to argue
    in favor of your original answer:<br>
    ''')
    form = webui.Form('reconsider')
    form.append(webui.Textarea('reasons'))
    form.append('<br>\n')
    l = dict(unchanged='I still prefer my original answer.',
             switched="I've decided my partner's answer is better (enter his/her name below).")
    form.append(webui.RadioSelection('status', list(enumerate(l))))
    add_confidence_choice(form)
    form.append("<br>\nYour partner's username:")
    form.append(webui.Input('partner'))
    form.append('<br>\n')
    doc.append(form)
    return str(doc)



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
        self._reconsiderHTML = build_reconsider_form()
        self.enableMathJax = enableMathJax
    
    def serve_question(self, question):
        self._question = question
        question.courseDB = self.courseDB
        if self.enableMathJax:
            question.doc.head.append('<script type="text/javascript" src="/MathJax/MathJax.js?config=TeX-AMS-MML_HTMLorMML"></script>\n')
        self._questionHTML = str(question)
        self.answer = question.answer
        self.prototype_form = question.prototype_form
        
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
