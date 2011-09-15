import webui

def login_form(action='login',
               text='Please login to PIPS using your username and UCLA ID:<br>\n',
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
                  entering your full name and UCLA ID:<br>\n'''):
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
    return str(doc)

