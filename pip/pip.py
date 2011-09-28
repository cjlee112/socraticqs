import cherrypy
import webui
import thread
import login
from coursedb import CourseDB
from monitor import TtyMonitor

def redirect(path='/', body=None, delay=0):
    'redirect browser, if desired after showing a message'
    s = '<HTML><HEAD>\n'
    s += '<meta http-equiv="Refresh" content="%d; url=%s">\n' % (delay, path)
    s += '</HEAD>\n'
    if body:
        s += '<BODY>%s</BODY>\n' % body
    s += '</HTML>\n'
    return s

class Server(object):
    '''provides dynamic interfaces for students and instructor.
    Intended to be run from Python console, retaining control via the
    console thread; the cherrypy server runs using background threads.'''
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
        self.registerAll = registerAll
        self._loginHTML = login.login_form()
        self._reloadHTML = redirect()
        self.questions = {}
        if questionFile:
            self.serve_question(self.courseDB.questions[0])
        self.monitor = TtyMonitor()
    
    def serve_question(self, question):
        'set the question to be posed to the students'
        self.question = question
        question.courseDB = self.courseDB
        self.questions[question.id] = question # add to our lookup
        
    def start(self):
        'start cherrypy server as background thread, retaining control of main thread'
        self.threadID = thread.start_new_thread(self.serve_forever, ())

    def serve_forever(self):
        cherrypy.quickstart(self, '/', 'cp.conf')

    # student interfaces
    def index(self):
        try:
            uid = cherrypy.session['UID']
        except KeyError:
            if self.registerAll:
                return self._registerHTML
            else:
                return self._loginHTML
            
        try:
            return self.question._viewHTML['answer']
        except AttributeError:
            return """The instructor has not yet assigned a question.
            Please click your browser's refresh button when your
            instructor tells you to load the first question."""
    index.exposed = True

    def login_form(self):
        return self._loginHTML
    login_form.exposed = True

    def login(self, username, uid):
        username = username.lower()
        try:
            uid = int(uid)
        except ValueError:
            return """Your UID must be an integer! Please click your
            browser's Back button and correct your UID."""
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
            self.courseDB.logout(cherrypy.session['UID'])
        except KeyError:
            s = 'Your session already timed out or you were not logged in.'
        s = 'You are now logged out.'
        return s + '<br>\nClick here to <A HREF="/">login</A> again.'
    logout.exposed = True

    def reconsider_form(self):
        return self._reconsiderHTML
    reconsider_form.exposed = True

    def view(self, stage=None, qid='', **kwargs):
        try:
            uid = cherrypy.session['UID']
        except KeyError:
            return '''You are not logged in!  Click here to
            <A HREF="/login">login</A>.'''
        try:
            q = self.questions[int(qid)]
        except (ValueError,KeyError):
            print 'ERROR: Unknown qid:', qid
            return '''An error occurred.  Please either try to resubmit your
            form, or skip to the next step.'''
        if stage != 'answer' and uid not in q.responses:
            return q._noResponseHTML
        try:
            return q._viewHTML[stage] # just return stored HTML
        except KeyError:
            if stage == 'cluster':
                return q.cluster_form(uid)
            print 'ERROR: Unknown stage:', stage
            return '''An error occurred.  Please skip to the next step.'''
    view.exposed = True

    def submit(self, stage=None, qid='', **kwargs):
        try:
            uid = cherrypy.session['UID']
        except KeyError:
            return '''You are not logged in!  Click here to
            <A HREF="/login">login</A>.'''
        try:
            q = self.questions[int(qid)]
        except (ValueError,KeyError):
            print 'ERROR: Unknown qid:', qid
            return '''An error occurred.  Please either try to resubmit your
            form, or skip to the next step.'''
        try:
            action = q.submitStages[stage]
        except KeyError:
            print 'ERROR: Unknown stage:', stage
            return '''An error occurred.  Please either try to resubmit your
            form, or skip to the next step.'''
        return action(uid, monitor=self.monitor, **kwargs)
    submit.exposed = True

    # instructor interfaces
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
        Once the students have entered their answers, click here to
        <A HREF="/start_round2">start round 2</A>.''' % question.title

    def _start_round2(self, **kwargs):
        if self.question.count_unclustered(): # need to do clustering
            return self.question.prototype_form(**kwargs)
        return '''Please wait until the students are done with
        round 2, then click here to
        <A HREF="/prototype_form">view initial results</A>.'''

    d = dict(admin='self._admin_page',
             start_question='self._start_question',
             start_round2='self._start_round2',
             prototype_form='self.question.prototype_form',
             add_prototypes='self.question.add_prototypes',
             cluster_report='self.question.cluster_report',
             correct='self.question.correct',
             add_correct='self.question.add_correct',
             analysis='self.question.analysis',
             save_responses='self.question.save_responses')
    for name,funcstr in d.items(): # create authenticated admin methods
        exec '''%s=lambda self, **kwargs:self.auth_admin(%s, **kwargs)
%s.exposed = True''' % (name, funcstr, name)
    del d # don't leave this cluttering the class attributes

    # test aurigma up support
    def aurigma_up(self, uid, PackageFileCount, **kwargs):
        print 'aurigma_up: uid', uid
        for i in range(int(PackageFileCount)):
            filename = kwargs['SourceName_%d' % i]
            print 'Writing', filename
            ofile = open(filename, 'wb')
            ofile.write(kwargs['File0_%d' % i].file.read())
            ofile.close()
    aurigma_up.exposed = True
        
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
