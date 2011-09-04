import cherrypy
import webui
import thread

class Question(object):
    def __init__(self, title, text, choices):
        doc = webui.Document(title)
        doc.add_text(text)
        form = webui.Form('answer')
        form.append(webui.Selection('choice', list(enumerate(choices))))
        form.append('<br>\n')
        form.append(webui.Data('Explain:'))
        form.append(webui.Input('reason', size=50))
        form.append('<br>\n')
        doc.append(form)
        self.doc = doc
        self.responses = {}

    def __str__(self):
        return str(self.doc)

    def answer(self, choice=None, reason=None):
        uid = cherrypy.session['UID']
        if not choice or not reason:
            pass
        self.responses[uid] = (choice, reason)
        return 'Thanks for answering! <A HREF="/">Continue</A>'
    answer.exposed = True

class QuestionUpload(object):
    def __init__(self, title, text, stem='q'):
        self.stem = stem
        doc = webui.Document(title)
        doc.add_text(text)
        form = webui.Form('answer')
        doc.add_text('''(write your answer on a sheet of paper, take a picture,
        and upload the picture using the button below).<br>\n''')
        form.append(webui.Upload('image'))
        form.append('<br>\n')
        doc.append(form)
        self.doc = doc
        self.responses = {}

    def __str__(self):
        return str(self.doc)

    def answer(self, image=None):
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

    def __init__(self):
        self._loginHTML = self.login_form()
        self._reloadHTML = redirect()
    
    def serve_question(self, question):
        self._question = question
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

    def login_form(self):
        doc = webui.Document('Login')
        doc.add_text('Please enter your UCLA ID:')
        doc.append('<br>\n')
        form = webui.Form('submit_uid')
        form.append(webui.Data('UID:'))
        form.append(webui.Input('uid', size=10))
        doc.append(form)
        return str(doc)

    def submit_uid(self, uid=None):
        if not uid:
            pass
        cherrypy.session['UID'] = uid
        return self._reloadHTML
    submit_uid.exposed = True

def test(title='Monty Hall',
         text='The probability of winning by switching your choice is:',
         choices=('1/3','1/2','2/3', 'Impossible to say')):
    q = Question(title, text, choices)
    s = PipRoot()
    s.serve_question(q)
    s.start()
    return s
