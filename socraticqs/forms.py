import webui

def login_form(action='login',
               text='Please login to Socraticqs using your username and Student ID:<br>\n',
               registerText='''<br>
               If you have never logged in, click here to
               <A HREF="/register_form">register</A>.
               '''):
    doc = webui.Document('Login')
    doc.add_text(text)
    form = webui.Form(action)
    form.append(webui.Data('username:'))
    form.append(webui.Input('username', size=10))
    form.append(webui.Data('<br>\nUID:'))
    form.append(webui.Input('uid', 'password', size=10))
    doc.append(form)
    doc.add_text(registerText)
    return str(doc)

def register_form(action='register',
                  text='''Please register by choosing a username, and
                  entering your full name and Student ID:<br>\n''',
                  loginText='''<br>
                  If you have already registered, click here to
                  <A HREF="/login_form">login</A>.
                  '''):
    doc = webui.Document('Register')
    doc.add_text(text)
    form = webui.Form(action)
    form.append(webui.Data('username:'))
    form.append(webui.Input('username', size=10))
    form.append(webui.Data('<br>\nFull Name (e.g. Joe Smith):'))
    form.append(webui.Input('fullname', size=20))
    form.append(webui.Data('<br>\nUID:'))
    form.append(webui.Input('uid', 'password', size=10))
    form.append(webui.Data('<br>\nRe-enter UID:'))
    form.append(webui.Input('uid2', 'password', size=10))
    doc.append(form)
    doc.add_text(loginText)
    return str(doc)

def add_confidence_choice(form, levels=('Just guessing', 'Not quite sure',
                                        'Pretty sure')):
    form.append('<br>\nHow confident are you in your answer?<br>\n')
    form.append(webui.RadioSelection('confidence', list(enumerate(levels))))
    
def build_reconsider_form(qid, bottom='', title='Reconsidering your answer'):
    'return HTML for standard form for round 2'
    doc = webui.Document(title)
    doc.add_text('''<B>Instructions</B>: As soon as your partner is
    ready, please take turns explaining why you think your
    answer is right, approximately one minute each.
    Then answer the following questions:<BR>
    ''')
    form = webui.Form('submit')
    form.append(webui.Input('qid', 'hidden', str(qid)))
    form.append(webui.Input('stage', 'hidden', 'reconsider'))
    d = dict(unchanged='I still prefer my original answer.',
             switched="I've decided my partner's answer is better (enter his/her name below).")
    form.append(webui.RadioSelection('status', d.items(),
                                     selected='unchanged'))
    add_confidence_choice(form)
    form.append("<br>\nYour partner's username (only needed if you prefer their answer):")
    form.append(webui.Input('partner'))
    form.append('<br>\n')
    doc.append(form)
    doc.add_text(bottom)
    return str(doc)

def build_assess_form(qid, errorModels=(), bottom='', title='Assessing your answer'):
    'return HTML for standard form for round 2'
    doc = webui.Document(title)
    doc.add_text('''How does your answer compare with the right answer?
    If your answer was different, please briefly explain below how your
    reasoning differed.''', 'B')
    form = webui.Form('submit')
    form.append(webui.Input('qid', 'hidden', str(qid)))
    form.append(webui.Input('stage', 'hidden', 'assess'))
    options = (('correct', 'Essentially the same.'),
               ('close', 'Close.'),
               ('different', 'Different.'))
    form.append(webui.RadioSelection('assessment', options))
    if errorModels:
        form.append("<br>\nDid you make any of the following common errors?<br>\n")
        form.append(webui.CheckboxSelection('errors', list(enumerate(errorModels))))
    form.append("<br>\nHow your reasoning differed:<br>\n")
    form.append(webui.Textarea('differences'))
    form.append('<br>\n')
    doc.append(form)
    doc.add_text(bottom)
    return str(doc)
