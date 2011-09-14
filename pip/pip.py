import cherrypy
import webui
import thread
import os.path
import sqlite3
import csv
import login
import time
from datetime import datetime, date

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
                 dbfile='course.db', createSchema=False):
        self.dbfile = dbfile
        self.logins = set()
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
        # need to cancel this session!!
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
                q = klass(t[1], t[2], t[3], t[4:]) # multiple choice answer
            else:
                q = klass(*t[1:])
            q.id = c.lastrowid
            l.append(q)
        self.questions = l

    def save_responses(self, question):
        'save all responses to this question to the database'
        def get_id(resp): # return None or the object's db id
            if resp:
                return resp.uid
        conn = sqlite3.connect(self.dbfile)
        c = conn.cursor()
        try:
            for r in question.responses.values(): # insert rows
                dt = datetime.fromtimestamp(r.timestamp)
                c.execute('''insert into responses values
                (NULL,?,?,?,?,?,?,datetime(?),?,?,?,?,?,?,?)''',
                          (r.uid, question.id, get_id(r.prototype),
                           question.is_correct(r),
                           r.get_answer(), r.confidence,
                           dt.isoformat().split('.')[0], r.reasons,
                           get_id(r.response2), r.confidence2,
                           get_id(r.finalVote), r.finalConfidence,
                           get_id(r.critiqueTarget), r.criticisms))
                r.id = c.lastrowid # record its primary key
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
    def get_answer(self):
        return self.choice
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
        try:
            return cmp(id(self.prototype), id(other.prototype))
        except AttributeError:
            return cmp(id(self), id(other))
    def __hash__(self):
        try:
            return id(self.prototype)
        except AttributeError:
            return id(self)

class TextResponse(ClusteredResponse):
    def save_data(self, text):
        self.text = text
    def get_answer(self):
        return self.text
    def __str__(self):
        return self.text + '<br>\n'

class ImageResponse(ClusteredResponse):
    def save_data(self, path, imageDir):
        self.path = path
        self.imageDir = imageDir
    def get_answer(self):
        return self.path
        ## ifile = open(os.path.join(self.imageDir, self.path), 'rb')
        ## data = ifile.read()
        ## ifile.close()
        ## return data
    def __str__(self):
        return '<IMG SRC="/images/%s"><br>\n' % self.path

class QuestionBase(object):
    def __init__(self, title, text, *args, **kwargs):
        self.title = title
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
                partnerUID = self.courseDB.userdict[partner.lower()].uid
            except KeyError:
                return """Sorry, the username you entered for your partner
                does not exist.  Please click your browser's back button
                to re-enter it!"""
            try:
                response.response2 = self.responses[partnerUID]
            except KeyError:
                return """Sorry, that username does not appear to
                have entered an answer!  Tell them to enter their answer, then
                click your browser's back button to resubmit your form."""
        else:
            response.response2 = None
        response.reasons = reasons
        response.confidence2 = confidence
        return '''Thanks! When your instructor asks you to, please click here to
            continue to <A HREF="%s">%s</A>.''' % (self._afterURL,
                                                   self._afterText)
    reconsider.exposed = True

    def prototype_form(self, offset=0, maxview=None,
                       title='Categorize Responses'):
        if not self.unclustered:
            return self.cluster_report()
        doc = webui.Document(title)
        if self.categories: # not empty
            doc.add_text('%d Categories' % len(self.categories), 'h1')
            for r in self.categories:
                doc.add_text(str(r))
        doc.add_text('%d Uncategorized Responses' % len(self.unclustered), 'h1')
        doc.add_text('''Choose one or more responses as new, distinct
        categories of student answers:<br>
        ''')
        l = list(self.unclustered)[offset:]
        if not maxview:
            maxview = self.maxview
        if maxview and len(l) > maxview:
            l = l[:maxview]
        form = webui.Form('add_prototypes')
        for r in l:
            form.append(webui.RadioSelection('resp_' + str(r.uid),
                                             (('add', str(r)),)))
        doc.append(form)
        if offset > 0:
            doc.add_text('<A HREF="/prototype_form?offset=%d&maxview=%d">[Previous %d]</A>\n'
                         % (max(0, offset - maxview), maxview, maxview))
        if maxview and len(self.unclustered) > offset + maxview:
            doc.add_text('<A HREF="/prototype_form?offset=%d&maxview=%d">[Next %d]</A>\n'
                         % (offset + maxview, maxview, maxview))
        return str(doc)

    def include_correct(self):
        'ensure that correctAnswer is in our categories'
        if self.correctAnswer not in self.categories:
            self.categories[self.correctAnswer] = []
            self.categoriesSorted = None # force this to update
            self.list_categories()

    def cluster_report(self):
        fmt = '%(answer)s<br><b>(%(tag)s answer chosen by %(n)d students)</b>'
        doc = webui.Document('Clustering Complete')
        doc.add_text('Done: %d responses in %d categories:'
                     % (len(self.responses), len(self.categories)), 'h1')
        try:
            p = len(self.categories.get(self.correctAnswer, ())) * 100. \
                / len(self.responses)
        except AttributeError:
            doc.add_text('Choose which answer is correct:')
            doc.append(self.get_choice_form('correct', False, 0, fmt))
            doc.add_text('''<br>If none of these are correct, click here
            to add the <A HREF="/add_correct">correct answer</A>.''')
        else:
            doc.add_text('%2.0f%% of students got the correct answer' % p)
            doc.append(self.get_choice_form('correct', False, 0, fmt))
            doc.add_text('Tell the students to proceed with their vote.')
            self.init_vote()
        return str(doc)

    def correct(self, choice):
        self.correctAnswer = self.categoriesSorted[int(choice)]
        self.init_vote()
        return '''Great.  Tell the students to proceed with their vote.'''

    def add_prototypes(self, **kwargs):
        n = 0
        for k,v in kwargs.items():
            if v == 'add':
                uid = int(k.split('_')[1])
                response = self.responses[uid]
                self.set_prototype(response)
                n += 1
        self.categoriesSorted = None # force this to update
        self._clusterFormHTML = self.build_cluster_form()
        return '''Added %d categories.  Tell the students to categorize
        themselves vs. your new categories.  When they are done,
        click here to <A HREF="/prototype_form">continue</A>.''' % n

    def list_categories(self):
        try:
            if self.categoriesSorted: # no need for update
                return self.categoriesSorted
        except AttributeError: # must create this list
            pass
        l = list(self.categories)
        l.sort()
        self.categoriesSorted = l
        return self.categoriesSorted

    def set_prototype(self, response, category=None):
        if category is None: # response is prototype for its own category
            category = response
            self.categories[category] = [category]
        else:
            self.categories[category].append(response)
        response.prototype = category
        self.unclustered.remove(response)

    def is_correct(self, response):
        return response == self.correctAnswer

    def cluster_form(self):
        uid = cherrypy.session['UID']
        response = self.responses[uid]
        if response in self.categories:
            return '''Your answer already matches a category.
            When your instructor asks you to, please click here to
            continue to the <A HREF="/vote_form">final vote</A>.'''
        return self._clusterFormHTML
    cluster_form.exposed = True

    def build_cluster_form(self, title='Cluster Your Answer'):
        doc = webui.Document(title)
        doc.add_text('''Either choose the answer that basically matches
        your original answer, or choose <B>None of the Above</B><br>
        ''')
        form = webui.Form('cluster')
        l = []
        for i,r in enumerate(self.list_categories()):
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
            round.  When your instructor asks you to, please click here to
            continue to the <A HREF="/cluster_form">next clustering round</A>.'''
        response = self.responses[uid]
        category = self.categoriesSorted[int(match)]
        self.set_prototype(response, category)
        return '''Thanks! When your instructor asks you to, please click here to
            continue to the <A HREF="/vote_form">final vote</A>.'''
    cluster.exposed = True

    def build_vote_form(self, form=None, title='Vote for the best answer',
                        text='Which of the following answers do you think is correct?<br>\n'):
        doc = webui.Document(title)
        doc.add_text(text)
        if form is None:
            form = self.get_choice_form()
        doc.append(form)
        return str(doc)
    def get_choice_form(self, action='vote', confidenceChoice=True,
                        maxreasons=2, fmt='%(answer)s', separator='<hr>\n'):
        form = webui.Form(action)
        l = []
        for i,category in enumerate(self.list_categories()):
            responses = self.categories.get(category, ())
            try:
                if self.is_correct(category):
                    tag = 'correct'
                else:
                    tag = 'wrong'
            except AttributeError: # correct answer not yet categorized
                tag = ''
            d = dict(n=len(responses), tag=tag, answer=str(category))
            s = fmt % d
            if maxreasons and responses:
                s += '<h3>Some arguments for this:</h3>\n'
                for r in responses[:maxreasons]:
                    s += '<LI>%s</LI>\n' % r.reasons
                separator = '<hr>\n'
            s += separator
            l.append((i, s))
        form.append(webui.RadioSelection('choice', l))
        if confidenceChoice:
            add_confidence_choice(form)
        form.append('<br>\n')
        return form
    def build_critique_form(self):
        form = self.get_choice_form('critique', False)
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
        
    def vote(self, choice, confidence):
        uid = cherrypy.session['UID']
        response = self.responses[uid]
        category = self.categoriesSorted[int(choice)]
        response.finalVote = category
        response.finalConfidence = confidence
        if category != response:
            return self._selfCritiqueHTML
        else:
            return self._critiqueHTML
    vote.exposed = True

    def critique(self, criticisms, choice):
        category = self.categoriesSorted[int(choice)]
        return self.save_critique(criticisms, category)
    critique.exposed = True
    
    def self_critique(self, criticisms):
        return self.save_critique(criticisms)
    self_critique.exposed = True
    
    def save_critique(self, criticisms, category=None):
        uid = cherrypy.session['UID']
        response = self.responses[uid]
        if category is None: # treat this as a self-critique
            category = response
        response.critiqueTarget = category
        response.criticisms = criticisms
        return '''Thanks! When your instructor asks you to, please click here to
        <A HREF="/">continue</A>.'''



class QuestionChoice(QuestionBase):
    def build_form(self, correctChoice, choices):
        'ask the user to choose an option'
        self.correctAnswer = MultiChoiceResponse(0, self, 0, int(correctChoice))
        self.choices = choices
        form = webui.Form('answer')
        l = []
        for i,s in enumerate(choices):
            l.append((i, '<B>%s</B>. %s' % (letters[i], s)))
        form.append(webui.RadioSelection('choice', l))
        add_confidence_choice(form)
        form.append('<br>\n')
        return form

    def answer(self, choice, confidence):
        uid = cherrypy.session['UID']
        response = MultiChoiceResponse(uid, self, confidence, choice)
        try: # append to its matching category
            self.categories[response].append(response)
            for r in self.categories:
                if r == response:
                    response.prototype = r
        except KeyError: # add this as a new category
            self.categories[response] = [response]
            response.prototype = response
        self.responses[uid] = response
        return '''Thanks for answering! When your instructor asks you to, please click here to
        <A HREF="/reconsider_form">continue</A>.'''
    answer.exposed = True

    def init_vote(self):
        'ensure all choices shown in final vote'
        for i in range(len(self.choices)):
            r = MultiChoiceResponse(i, self, 0, i)
            if r not in self.categories:
                self.categories[r] = []
        self.categoriesSorted = None # force this to update
        self.list_categories()
        QuestionBase.init_vote(self)

    _afterURL = '/vote_form'
    _afterText = 'the final vote'
        
class QuestionText(QuestionBase):
    def build_form(self, correctText,
                   instructions=r'''(Briefly state your answer to the question
    in the box below.  You may enter latex equations by enclosing them in
    pairs of dollar signs, e.g. \$\$c^2=a^2+b^2\$\$).<br>
    ''', maxview=100):
        'ask the user to enter a text answer'
        self._correctText = correctText
        self.maxview = maxview
        self.doc.append(webui.Data(instructions))
        form = webui.Form('answer')
        form.append(webui.Textarea('answer'))
        add_confidence_choice(form)
        form.append('<br>\n')
        return form

    def answer(self, answer, confidence):
        'receive text answer from user'
        uid = cherrypy.session['UID']
        response = TextResponse(uid, self, confidence, answer)
        self.unclustered.add(response) # initially not categorized
        self.responses[uid] = response
        return '''Thanks for answering!  When your instructor asks you to, please click here to
        <A HREF="/reconsider_form">continue</A>.'''
    answer.exposed = True

    def add_correct(self):
        self.correctAnswer = TextResponse(0, self, 0, self._correctText)
        self.include_correct()
        self.init_vote()
        return '''Great.  Tell the students to proceed with their vote.'''

    _afterURL = '/cluster_form'
    _afterText = 'categorize your answer'

class QuestionUpload(QuestionBase):
    def build_form(self, correctFile, stem='q',
                   instructions='''(write your answer on a sheet of paper, take a picture,
        and upload the picture using the button below).<br>\n''',
                   imageDir='static/images', maxview=10):
        'ask the user to upload an image file'
        self._correctFile = correctFile
        self.maxview = maxview
        self.stem = stem
        self.imageDir = imageDir
        self.doc.append(webui.Data(instructions))
        form = webui.Form('answer')
        form.append(webui.Upload('image'))
        add_confidence_choice(form)
        form.append('<br>\n')
        return form

    def answer(self, image, confidence):
        'receive uploaded image file from user'
        uid = cherrypy.session['UID']
        fname = self.stem + str(len(self.responses)) + '_' + image.filename
        ifile = open(os.path.join(self.imageDir, fname), 'wb')
        ifile.write(image.file.read())
        ifile.close()
        response = ImageResponse(uid, self, confidence, fname, self.imageDir)
        self.unclustered.add(response) # initially not categorized
        self.responses[uid] = response
        return '''Thanks for answering!  When your instructor asks you to, please click here to
        <A HREF="/reconsider_form">continue</A>.'''
    answer.exposed = True

    def add_correct(self):
        self.correctAnswer = ImageResponse(0, self, 0, self._correctFile,
                                           self.imageDir)
        self.include_correct()
        self.init_vote()
        return '''Great.  Tell the students to proceed with their vote.'''

    _afterURL = '/cluster_form'
    _afterText = 'categorize your answer'


questionTypes = dict(mc=QuestionChoice,
                     text=QuestionText,
                     image=QuestionUpload)

def add_confidence_choice(form, levels=('Just guessing', 'Not quite sure',
                                        'Pretty sure')):
    form.append('<br>\nHow confident are you in your answer?<br>\n')
    form.append(webui.RadioSelection('confidence', list(enumerate(levels))))
    

def redirect(path='/', body=None, delay=0):
    s = '<HTML><HEAD>\n'
    s += '<meta http-equiv="Refresh" content="%d; url=%s">\n' % (delay, path)
    s += '</HEAD>\n'
    if body:
        s += '<BODY>%s</BODY>\n' % body
    s += '</HTML>\n'
    return s

def build_reconsider_form(title='Reconsidering your answer'):
    doc = webui.Document(title)
    doc.add_text('''Briefly state the key points that you used to argue
    in favor of your original answer:<br>
    ''')
    form = webui.Form('reconsider')
    form.append(webui.Textarea('reasons'))
    form.append('<br>\n')
    d = dict(unchanged='I still prefer my original answer.',
             switched="I've decided my partner's answer is better (enter his/her name below).")
    form.append(webui.RadioSelection('status', d.items()))
    add_confidence_choice(form)
    form.append("<br>\nYour partner's username:")
    form.append(webui.Input('partner'))
    form.append('<br>\n')
    doc.append(form)
    return str(doc)



class PipRoot(object):
    _cp_config = {'tools.sessions.on': True}

    def __init__(self, questionFile, enableMathJax=True, registerAll=False,
                 adminIP='127.0.0.1', **kwargs):
        self.enableMathJax = enableMathJax
        if enableMathJax:
            webui.Document._defaultHeader = '''<script type="text/x-mathjax-config">
              MathJax.Hub.Config({
                tex2jax: {
                  processEscapes: true
                }
              });
            </script>
            <script type="text/javascript" src="/MathJax/MathJax.js?config=TeX-AMS-MML_HTMLorMML"></script>
            '''
        self.adminIP = adminIP
        self.courseDB = CourseDB(questionFile, **kwargs)
        self._registerHTML = login.register_form()
        if registerAll:
            self._loginHTML = self._registerHTML
        else:
            self._loginHTML = login.login_form()
        self._reloadHTML = redirect()
        self._reconsiderHTML = build_reconsider_form()
        if questionFile:
            self.serve_question(self.courseDB.questions[0])
    
    def serve_question(self, question):
        self.question = question
        question.courseDB = self.courseDB
        self._questionHTML = str(question)
        self.answer = question.answer
        self.reconsider = question.reconsider
        self.cluster_form = question.cluster_form
        self.vote = question.vote
        self.critique = question.critique
        self.self_critique = question.self_critique
        
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
        username = username.lower()
        try:
            uid = int(uid)
        except ValueError:
            return 'Your UID must be an integer! <A HREF="/">Continue</A>'
        try:
            self.courseDB.authenticate(uid, username)
        except ValueError, e:
            return str(e) + ' <A HREF="/">Continue</A>'
        self.courseDB.login(uid, username)
        return self._reloadHTML
    login.exposed = True

    def register_form(self):
        return self._registerHTML
    register_form.exposed = True

    def register(self, username, fullname, uid, uid2):
        username = username.lower()
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
        self.courseDB.login(uid, username)
        return msg + '. <A HREF="/">Continue</A>'
    register.exposed = True

    def logout(self):
        'close this session and remove from active logins list'
        try:
            self.courseDB.logout()
        except KeyError:
            return 'Your session already timed out or you were not logged in.'
        return 'You are now logged out.'
    logout.exposed = True

    def reconsider_form(self):
        return self._reconsiderHTML
    reconsider_form.exposed = True

    def vote_form(self):
        try:
            return self.question._voteHTML
        except AttributeError:
            return '''Sorry, not all answers have been categorized yet.
            Please wait until your instructor asks you to click here
            to <A HREF="/vote_form">continue</A>.'''
    vote_form.exposed = True

    # admin interfaces
    def auth_admin(self, func, **kwargs):
        if cherrypy.request.remote.ip == self.adminIP:
            return func(**kwargs)
        else:
            cherrypy.response.status = 401
            return '<h1>Access denied</h1>'

    def _admin_page(self):
        doc = webui.Document('PIPS Console')
        doc.add_text('%d students logged in.' % len(self.courseDB.logins))
        doc.add_text('Concept Tests', 'h1')
        for i,q in enumerate(self.courseDB.questions):
            doc.add_text('<A HREF="/start_question?q=%d">%s</A>'
                         % (i, q.title), 'LI')
        return str(doc)

    def _start_question(self, q):
        question = self.courseDB.questions[int(q)]
        self.serve_question(question)
        return '''Successfully setup %s.
        Once the students have entered their answers,
        click here to proceed to the
        <A HREF="/prototype_form">analysis page</A>.''' % question.title

    d = dict(admin='self._admin_page',
             prototype_form='self.question.prototype_form',
             add_prototypes='self.question.add_prototypes',
             correct='self.question.correct',
             add_correct='self.question.add_correct',
             start_question='self._start_question')
    for name,funcstr in d.items(): # create authenticated admin methods
        exec '''%s=lambda self, **kwargs:self.auth_admin(%s, **kwargs)
%s.exposed = True''' % (name, funcstr, name)
    del d # don't leave this cluttering the class attributes
        
def test(title='Monty Hall',
         text=r'''The probability of winning by switching your choice is:
         $$x = {-b \pm \sqrt{b^2-4ac} \over 2a}.$$''',
         choices=('1/3','1/2','2/3', 'Impossible to say'), tryText=True):
    if tryText:
        q = QuestionText('monty hall', text, '2/3')
    else:
        q = QuestionChoice(title, text, 2, choices)
    s = PipRoot(True)
    s.serve_question(q)
    s.start()
    return s
