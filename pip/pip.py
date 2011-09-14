import cherrypy
import webui
import thread
import os.path
import sqlite3
import csv
import login
import time
from datetime import datetime

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
        self.save_csv_to_db(path, self.insert_students, self.make_student_dict)

    def insert_students(self, users, c):
        for uid,fullname in users:
            c.execute('insert into students values (?,?,NULL,date("now"),"admin")',
                      (uid, fullname))

    def save_csv_to_db(self, path, func, postfunc=None):
        ifile = open(path, 'Ub')
        try:
            rows = csv.reader(ifile)
            conn = sqlite3.connect(self.dbfile)
            c = conn.cursor()
            try:
                func(rows, c)
                conn.commit()
                if postfunc:
                    postfunc(c)
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
        'execute a change to the db and commit it'
        conn = sqlite3.connect(self.dbfile)
        c = conn.cursor()
        try:
            c.execute(sql, args)
            conn.commit()
        finally:
            c.close()
            conn.close()

    def load_question_file(self, path):
        'read from CSV file to self.questions, and save to database'
        self.save_csv_to_db(path, self.insert_questions)

    def insert_questions(self, questions, c):
        l = []
        for t in questions:
            c.execute('insert into questions values (NULL,?,?,date("now"))',
                      t[:2])
            klass = questionTypes[t[0]]
            if t[0] == 'mc':
                q = klass(t[1], t[2], t[3:]) # multiple choice answer
            else:
                q = klass(*t[1:])
            q.id = c.lastrowid
            l.append(q)
        self.questions = l

    def save_responses(self, question):
        'save all responses to this question to the database'
        def get_id(resp): # return None or the object's db id
            if resp:
                return resp.id
        conn = sqlite3.connect(self.dbfile)
        c = conn.cursor()
        try:
            for r in question.responses.values(): # insert rows
                dt = datetime.fromtimestamp(r.timestamp)
                c.execute('''insert into responses values
                (NULL,?,?,NULL,?,?,datetime(?),?,NULL,?,NULL,?,NULL,?)''',
                          (r.uid, question.id, r.get_answer(), r.confidence,
                           dt.isoformat().split('.')[0], r.reasons,
                           r.confidence2, r.finalConfidence, r.criticisms))
                r.id = c.lastrowid # record its primary key
            for r in question.responses.values(): # now set cross-reference IDs
                c.execute('''update responses set cluster_id=?,
                switched_id=?, final_id=?, critique_id=?
                where id=?''', (get_id(r.prototype), get_id(r.response2),
                                get_id(r.finalVote), get_id(r.critiqueTarget),
                                r.id))
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
        return cmp(id(self.prototype), id(other.prototype))
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
    def save_data(self, stem, image):
        self.fname = stem + '_' + image.filename
        ifile = open(self.fname, 'wb')
        ifile.write(image.file.read())
        ifile.close()
    def get_answer(self):
        ifile = open(self.fname, 'rb')
        data = ifile.read()
        ifile.close()
        return data

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

    def save_reasons(self, reasons, status, confidence, partner):
        uid = cherrypy.session['UID']
        response = self.responses[uid]
        if status == 'switched':
            try:
                partnerUID = self.courseDB.userdict[partner].uid
            except KeyError:
                raise BadUsernameError("""Sorry, the username you entered for your partner
                does not exist.  Please re-enter it!
                <A HREF='/reconsider_form'>Continue</A>.""")
            response.response2 = self.responses[partnerUID]
        else:
            response.response2 = None
        response.reasons = reasons
        response.confidence2 = confidence

    def reconsider(self, reasons, status, confidence, partner):
        try:
            self.save_reasons(reasons, status, confidence, partner)
        except BadUsernameError, e:
            return str(e)
        return '''Thanks! When your instructor asks you to, please click here to
            continue to <A HREF="%s">%s</A>.''' % (self._afterURL,
                                                   self._afterText)
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
        self.init_vote()
        s = '<h1>Done</h1>%d responses in %d categories:' \
            % (len(self.responses), len(self.categories))
        return s

    def add_prototypes(self, **kwargs):
        n = 0
        for k,v in kwargs.items():
            if v == 'add':
                uid = int(k.split('_')[1])
                response = self.responses[uid]
                self.set_prototype(response)
                n += 1
        l = list(self.categories)
        l.sort()
        self.categoriesSorted = l
        self._clusterFormHTML = self.build_cluster_form()
        return '''Added %d categories.  Tell the students to categorize
        themselves vs. your new categories.  When they are done,
        click here to <A HREF="/prototype_form">continue</A>.''' % n
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
                        maxreasons=2):
        form = webui.Form(action)
        l = []
        for i,category in enumerate(self.categoriesSorted):
            s = str(category)
            if maxreasons:
                responses = self.categories[category][:maxreasons]
                s += '<h3>Some arguments for this:</h3>\n'
                for r in responses:
                    s += '<LI>%s</LI>\n' % r.reasons
                s += '<hr>\n'
            l.append((i, str(r)))
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
    def build_form(self, choices):
        'ask the user to choose an option'
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

    _afterURL = '/vote_form'
    _afterText = 'the final vote'
        
class QuestionText(QuestionBase):
    def build_form(self, instructions=r'''(Briefly state your answer to the question
    in the box below.  You may enter latex equations by enclosing them in
    pairs of dollar signs, e.g. \$\$c^2=a^2+b^2\$\$).<br>
    '''):
        'ask the user to enter a text answer'
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

    _afterURL = '/cluster_form'
    _afterText = 'categorize your answer'

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
        return '''Thanks for answering!  When your instructor asks you to, please click here to
        <A HREF="/reconsider_form">continue</A>.'''
    answer.exposed = True

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
    
    def serve_question(self, question):
        self.question = question
        question.courseDB = self.courseDB
        self._questionHTML = str(question)
        self.answer = question.answer
        self.reconsider = question.reconsider
        self.prototype_form = question.prototype_form
        self.add_prototypes = question.add_prototypes
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

    def reconsider_form(self):
        return self._reconsiderHTML
    reconsider_form.exposed = True

    def vote_form(self):
        return self.question._voteHTML
    vote_form.exposed = True
        
def test(title='Monty Hall',
         text=r'''The probability of winning by switching your choice is:
         $$x = {-b \pm \sqrt{b^2-4ac} \over 2a}.$$''',
         choices=('1/3','1/2','2/3', 'Impossible to say'), tryText=True):
    if tryText:
        q = QuestionText('monty hall', text)
    else:
        q = QuestionChoice(title, text, choices)
    s = PipRoot(True)
    s.serve_question(q)
    s.start()
    return s
