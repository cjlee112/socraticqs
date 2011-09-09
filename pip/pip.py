import cherrypy
import webui
import thread

        
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

    def __init__(self, enableMathJax=False):
        self._loginHTML = self.login_form()
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
         text=r'''The probability of winning by switching your choice is:
         $$x = {-b \pm \sqrt{b^2-4ac} \over 2a}.$$''',
         choices=('1/3','1/2','2/3', 'Impossible to say')):
    q = QuestionChoice(title, text, choices)
    s = PipRoot(True)
    s.serve_question(q)
    s.start()
    return s
