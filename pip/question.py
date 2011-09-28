import cherrypy
import os.path
import time
import webui
import subprocess

letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

_missing_arg_msg = '''You forgot to enter some required information into
the form.  Please click the Back button in your browser to enter
the required information.'''

def missing_params(*args):
    for arg in args:
        if arg is None:
            return True

def add_confidence_choice(form, levels=('Just guessing', 'Not quite sure',
                                        'Pretty sure')):
    form.append('<br>\nHow confident are you in your answer?<br>\n')
    form.append(webui.RadioSelection('confidence', list(enumerate(levels))))
    
def build_reconsider_form(qid, bottom='', title='Reconsidering your answer'):
    'return HTML for standard form for round 2'
    doc = webui.Document(title)
    doc.add_text('''Briefly state the key points that you used to argue
    in favor of your original answer:<br>
    ''')
    form = webui.Form('submit')
    form.append(webui.Input('qid', 'hidden', str(qid)))
    form.append(webui.Input('stage', 'hidden', 'reconsider'))
    form.append(webui.Textarea('reasons'))
    form.append('<br>\n')
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


class Response(object):
    'subclass this to supply different storage and representation methods'
    def __init__(self, uid, question, confidence, *args, **kwargs):
        self.uid = uid
        self.question = question
        self.timestamp = time.time()
        self.confidence = int(confidence)
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
        try:
            return cmp(self.choice, other.choice)
        except AttributeError:
            return cmp(id(self), id(other))
    def __hash__(self):
        try:
            return hash(self.choice)
        except AttributeError:
            return id(self)

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
    def save_data(self, path, text, imageDir, hideMe=False):
        self.path = path
        self.text = text
        self.imageDir = imageDir
        self.hideMe = hideMe
    def get_answer(self):
        return self.text
        ## ifile = open(os.path.join(self.imageDir, self.path), 'rb')
        ## data = ifile.read()
        ## ifile.close()
        ## return data
    def __str__(self):
        s = ''
        if self.hideMe:
            s += self.hideMe + '<br>\n'
        elif self.path:
            s += '<IMG SRC="/images/%s"><br>\n' % self.path
        if self.text:
            s += self.text + '<br>\n'
        return s

class QuestionBase(object):
    def __init__(self, questionID, title, text, *args, **kwargs):
        self.id = questionID
        self.title = title
        self.text = text
        for attr in ('hasReasons', 'isClustered', 'noMatch', 'hasFinalVote',
                     'hasCritique'):
            setattr(self, attr, set()) # initialize answer counters
        doc = webui.Document(title)
        self.doc = doc
        doc.add_text(text)
        form = webui.Form('submit')
        form.append(webui.Input('qid', 'hidden', str(self.id)))
        form.append(webui.Input('stage', 'hidden', 'answer'))
        self.build_form(form, *args, **kwargs)
        doc.append(form)
        doc.add_text(self._navHTML)
        self.responses = {}
        self.categories = {}
        d = {}
        for attr in self._stages: # initialize submission action dict
            d[attr] = getattr(self, attr)
        self.submitStages = d
        self._viewHTML = {
            'answer': str(doc),
            'reconsider': build_reconsider_form(questionID, self._navHTML),
            'vote': '''Sorry, not all answers have been categorized yet.
            Please wait until your instructor asks you to click here
            to <A HREF="%s">continue</A>.%s'''
            % (self.get_url('vote'), self._navHTML),
            'critique': 'Sorry, we are not yet ready to critique answers.'
            + self._navHTML,
            'self_critique': 'Sorry, we are not yet ready to critique answers.'
            + self._navHTML
            }
        self._clusterFormHTML = \
            '''No categories have yet been added.
            When your instructor asks you to, please click here to
            continue to <A HREF="%s">categorize your answer</A>.%s''' \
            % (self.get_url('cluster'), self._navHTML)
        self._matchedHTML = \
            '''Your answer already matches a category.
            When your instructor asks you to, please click here to
            continue to the <A HREF="%s">final vote</A>.%s''' \
            % (self.get_url('vote'), self._navHTML)


    _stages = ('answer', 'reconsider', 'cluster', 'vote', 'critique',
               'self_critique')

    def __str__(self):
        return str(self.doc)

    # status reporting functions
    def answer_monitor(self, monitor):
        if monitor:
            monitor.message('answers: %d of %d total'
                            % (len(self.responses), len(self.courseDB.logins)))
    def cluster_monitor(self, monitor):
        if monitor:
            monitor.message('clustered: %d, %d NOT, of %d total' 
                            % (len(self.isClustered), len(self.noMatch),
                               len(self.responses)))

    # student interfaces
    def get_url(self, stage, action='view'):
        return '/%s?qid=%d&stage=%s' % (action, self.id, stage)

    def nav_html(self, cluster=True):
        s = '''<HR>
        <A HREF="/">START</A> &gt
        <A HREF="%s">DISCUSS</A> &gt
        ''' % self.get_url('reconsider')
        if cluster:
            s += '<A HREF="%s">CATEGORIZE</A> &gt' % self.get_url('cluster')
        s += '''
        <A HREF="%s">VOTE</A> &gt
        <A HREF="%s">CRITIQUE</A>
        ''' % (self.get_url('vote'), self.get_url('critique'))
        return s
    
    def _no_response_msg(self):
        msg = '''Sorry, you first need to submit an answer
        to this question, because I can find no record of your
        answer.  Please click here to
        <A HREF="%s">continue</A>.''' % self.get_url('answer')
        return msg + self._navHTML

    def reconsider(self, uid, reasons=None, status=None, confidence=None,
                   partner=None, monitor=None):
        if missing_params(status, confidence, partner) or not reasons:
            return _missing_arg_msg
        try:
            response = self.responses[uid]
        except KeyError:
            return self._no_response_msg()
        if status == 'switched':
            try:
                partnerUID = self.courseDB.userdict[partner.lower()].uid
            except KeyError:
                return """Sorry, the username you entered for your partner
                does not exist.  Please click your browser's back button
                to re-enter it!""" + self._navHTML
            try:
                response.response2 = self.responses[partnerUID]
            except KeyError:
                return """Sorry, that username does not appear to
                have entered an answer!  Tell them to enter their answer, then
                click your browser's back button to resubmit your form.""" \
                + self._navHTML
        else:
            response.response2 = response
        response.reasons = reasons
        response.confidence2 = int(confidence)
        self.hasReasons.add(uid)
        if monitor:
            monitor.message('recons: %d of %d total'
                            % (len(self.hasReasons), len(self.responses)))
        ## self.alert_if_done()
        return '''Thanks! When your instructor asks you to, please click here to
            continue to <A HREF="%s">%s</A>.%s''' \
            % (self._afterURL, self._afterText, self._navHTML)

    def cluster_form(self, uid):
        try:
            response = self.responses[uid]
        except KeyError:
            return self._no_response_msg()
        if response in self.categories:
            return self._matchedHTML
        else:
            return self._clusterFormHTML

    def build_cluster_form(self, title='Cluster Your Answer'):
        doc = webui.Document(title)
        doc.add_text('''Either choose the answer that basically matches
        your original answer, or choose <B>None of the Above</B><br>
        ''')
        form = webui.Form('submit')
        form.append(webui.Input('qid', 'hidden', str(self.id)))
        form.append(webui.Input('stage', 'hidden', 'cluster'))
        l = []
        for i,r in enumerate(self.list_categories()):
            l.append((i, str(r)))
        l.append(('none', 'None of the above'))
        form.append(webui.RadioSelection('match', l))
        form.append('<br>\n')
        doc.append(form)
        doc.add_text(self._navHTML)
        return str(doc)

    def cluster(self, uid, match=None, monitor=None):
        if missing_params(match):
            return _missing_arg_msg
        if match == 'none':
            self.noMatch.add(uid)
            self.cluster_monitor(monitor)
            return '''OK.  Hopefully we can cluster your answer in the next
            round.  When your instructor asks you to, please click here to
            continue to the <A HREF="%s">next clustering round</A>.%s''' \
            % (self.get_url('cluster'), self._navHTML)
        try:
            response = self.responses[uid]
        except KeyError:
            return self._no_response_msg()
        if hasattr(response, 'prototype'):
            return '''Sorry, but your answer has already been categorized!
            When your instructor asks you to, please click here to
            continue to the <A HREF="%s">final vote</A>.%s''' \
            % (self.get_url('vote'), self._navHTML)
        category = self.categoriesSorted[int(match)]
        self.set_prototype(response, category)
        self.cluster_monitor(monitor)
        return '''Thanks! When your instructor asks you to, please click here to
            continue to the <A HREF="%s">final vote</A>.%s''' \
            % (self.get_url('vote'), self._navHTML)

    def build_vote_form(self, form=None, title='Vote for the best answer',
                        text='''<h1>Vote</h1>
                        Which of the following answers do you think is correct?
                        <br>'''):
        doc = webui.Document(title)
        doc.add_text(text)
        if form is None:
            form = self.get_choice_form()
        doc.append(form)
        doc.add_text(self._navHTML)
        return str(doc)

    def get_choice_form(self, action='vote', confidenceChoice=True,
                        maxreasons=2, fmt='%(answer)s', separator='<hr>\n',
                        useSubmit=True):
        if useSubmit:
            form = webui.Form('submit')
            form.append(webui.Input('qid', 'hidden', str(self.id)))
            form.append(webui.Input('stage', 'hidden', action))
        else:
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
                    try:
                        s += '<LI>%s</LI>\n' % r.reasons
                    except AttributeError:
                        pass
                separator = '<hr>\n'
            s += separator
            l.append((i, s))
        form.append(webui.RadioSelection('choice', l))
        if confidenceChoice:
            add_confidence_choice(form)
        form.append('<br>\n')
        return form

    def vote(self, uid, choice=None, confidence=None, monitor=None):
        if missing_params(choice, confidence):
            return _missing_arg_msg
        try:
            response = self.responses[uid]
        except KeyError:
            return self._no_response_msg()
        try:
            category = self.categoriesSorted[int(choice)]
        except (AttributeError,IndexError,ValueError):
            return 'Please go back and resubmit your vote when your instructor says to.' \
                   + self._navHTML
        response.finalVote = category
        response.finalConfidence = int(confidence)
        self.hasFinalVote.add(uid)
        if monitor:
            monitor.message('voted: %d of %d total'
                            % (len(self.hasFinalVote), len(self.responses)))
        if hasattr(response, 'prototype') and category != response:
            return self._viewHTML['self_critique']
        else:
            return self._viewHTML['critique']

    def build_critique_form(self):
        form = self.get_choice_form('critique', False)
        form.append('<br>\nBriefly state what you think is wrong with this answer:<br>\n')
        form.append(webui.Textarea('criticisms'))
        form.append('<br>\n')
        return self.build_vote_form(form, 'Choose an answer to critique',
                                    '''<h1>Critique</h1>
                                    Choose one of the following answers to critique:
                                    <br>''')

    def critique(self, uid, criticisms=None, choice=None, monitor=None):
        if missing_params(criticisms, choice):
            return _missing_arg_msg
        try:
            category = self.categoriesSorted[int(choice)]
        except (AttributeError,IndexError,ValueError):
            return 'Please go back and resubmit your critique when your instructor says to' \
                   + self._navHTML
        return self.save_critique(uid, criticisms, category, monitor)

    def build_self_critique_form(self, title='Critique your original answer',
                                 text='''<h1>Critique</h1>
                                 Briefly state what you think was wrong with your original answer:
                                 <br>''',
                                 action='self_critique'):
        doc = webui.Document(title)
        doc.add_text(text)
        form = webui.Form('submit')
        form.append(webui.Input('qid', 'hidden', str(self.id)))
        form.append(webui.Input('stage', 'hidden', action))
        form.append(webui.Textarea('criticisms'))
        form.append('<br>\n')
        doc.append(form)
        doc.add_text(self._navHTML)
        return str(doc)
    
    def self_critique(self, uid, criticisms, monitor=None):
        return self.save_critique(uid, criticisms, monitor=monitor)
    
    def save_critique(self, uid, criticisms, category=None, monitor=None):
        try:
            response = self.responses[uid]
        except KeyError:
            return self._no_response_msg()
        if category is None: # treat this as a self-critique
            category = response
        response.critiqueTarget = category
        response.criticisms = criticisms
        self.hasCritique.add(uid)
        if monitor:
            monitor.message('critique: %d of %d total'
                            % (len(self.hasCritique), len(self.responses)))
        ## self.alert_if_done()
        return '''Thanks! When your instructor asks you to, please click here to
        <A HREF="/">continue</A>.''' + self._navHTML

    # instructor interfaces
    def prototype_form(self, offset=0, maxview=None,
                       title='Categorize Responses'):
        offset = int(offset)
        unclustered = self.count_unclustered()
        if unclustered == 0:
            return self.cluster_report()
        doc = webui.Document(title)
        if self.categories: # not empty
            doc.add_text('%d Categories' % len(self.categories), 'h1')
            for r in self.categories:
                doc.add_text(str(r))
        doc.add_text('%d Uncategorized Responses' % unclustered, 'h1')
        doc.add_text('''Choose one or more responses as new, distinct
        categories of student answers:<br>
        ''')
        l = list(self.iter_unclustered())[offset:]
        if not maxview:
            try:
                maxview = self.maxview
            except AttributeError:
                maxview = 10
        maxview = int(maxview)
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
        if maxview and unclustered > offset + maxview:
            doc.add_text('<A HREF="/prototype_form?offset=%d&maxview=%d">[Next %d]</A>\n'
                         % (offset + maxview, maxview, maxview))
        doc.add_text('''<br>If you want to "declare victory", click here to
        proceed to the <A HREF="/cluster_report">cluster report</A>.''')
        return str(doc)

    def include_correct(self):
        'ensure that correctAnswer is in our categories'
        if self.correctAnswer not in self.categories:
            self.categories[self.correctAnswer] = []
            self.list_categories(True) # force this to update

    def count_unclustered(self):
        return len(self.responses) - len(self.isClustered)

    def iter_unclustered(self):
        for r in self.responses.values():
            if not hasattr(r, 'prototype'):
                yield r

    _gotoVoteHTML = '''Tell the students to proceed with their vote.
    Finally, click here to <A HREF="/analysis">analyze the results</A>.'''

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
            doc.append(self.get_choice_form('correct', False, 0, fmt,
                                            useSubmit=False))
            doc.add_text('''<br>If none of these are correct, click here
            to add the <A HREF="/add_correct">correct answer</A>
            given by the instructor.''')
        else:
            doc.add_text('%2.0f%% of students got the correct answer<hr>' % p)
            doc.append(self.get_choice_form('correct', False, 0, fmt))
            doc.add_text(self._gotoVoteHTML)
            self.init_vote()
        return str(doc)

    def correct(self, choice):
        self.correctAnswer = self.categoriesSorted[int(choice)]
        self.init_vote()
        return 'Great.  ' + self._gotoVoteHTML

    def add_prototypes(self, **kwargs):
        n = 0
        for k,v in kwargs.items():
            if v == 'add':
                uid = int(k.split('_')[1])
                response = self.responses[uid]
                self.set_prototype(response)
                n += 1
        self.list_categories(True) # force this to update
        self._clusterFormHTML = self.build_cluster_form()
        self.noMatch.clear()
        return '''Added %d categories.  Tell the students to categorize
        themselves vs. your new categories.  When they are done,
        click here to <A HREF="/prototype_form">continue</A>.''' % n

    def list_categories(self, update=False):
        if not update and getattr(self, 'categoriesSorted', False):
            return self.categoriesSorted # no need for update
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
        self.isClustered.add(response.uid)

    def is_correct(self, response):
        try:
            return response == self.correctAnswer
        except AttributeError:
            return None

    def init_vote(self):
        self._viewHTML['vote'] = self.build_vote_form()
        self._viewHTML['critique'] = self.build_critique_form()
        self._viewHTML['self_critique'] = self.build_self_critique_form()
        
    def count_rounds(self):
        'return vote counts for the three rounds of response'
        d1 = {}
        d2 = {}
        d3 = {}
        for r in self.responses.values():
            d1[r] = d1.get(r, 0) + 1
            r2 = getattr(r, 'response2', None)
            d2[r2] = d2.get(r2, 0) + 1
            r3 = getattr(r, 'finalVote', None)
            d3[r3] = d3.get(r3, 0) + 1
        return d1, d2, d3

    def analysis(self, title='Final Results'):
        f = 100. / len(self.responses)
        def perc(d, k):
            return '%1.0f%%' % (d.get(k, 0) * f)
        doc = webui.Document(title)
        d1, d2, d3 = self.count_rounds()
        t = webui.Table('%d Responses' % len(self.responses),
                        ('answer','initial', 'revised', 'final'))
        for i,category in enumerate(self.categoriesSorted):
            a = letters[i]
            if category == self.correctAnswer: # bold the correct answer
                a = '<B>' + a + '</B>'
            t.append((a, perc(d1, category), perc(d2, category),
                      perc(d3, category)))
        t.append(('NR', '0%', perc(d2, None), perc(d3, None)))
        doc.append(t)
        doc.add_text('Reasons and Critiques', 'h1')
        for i,category in enumerate(self.categoriesSorted):
            doc.add_text('Answer ' + letters[i], 'h2')
            doc.add_text(str(category))
            if self.categories[category]:
                doc.add_text('Reasons Given for this Answer', 'h3')
                for r in self.categories[category]:
                    reasons = getattr(r, 'reasons', None)
                    if reasons:
                        doc.add_text(reasons, 'LI')
            l = []
            for r in self.responses.values():
                if getattr(r, 'critiqueTarget', None) == category \
                   and getattr(r, 'criticisms', None):
                    l.append(r.criticisms)
            if l:
                doc.add_text('Critiques of this Answer', 'h3')
                for s in l:
                    doc.add_text(s, 'LI')
            doc.add_text('<HR>\n')
        doc.add_text('''Click here to <A HREF="/save_responses">save 
        all student responses to the database</A>.''')
        return str(doc)

    def save_responses(self):
        n = self.courseDB.save_responses(self)
        return '''Saved %d responses.  Click here to go to the
        <A HREF='/admin'>PIPS console</A>.''' % n

    ## def alert_if_done(self, initial=False):
    ##     self.answered.add(cherrypy.session['UID'])
    ##     if initial:
    ##         try:
    ##             if len(self.answered) == len(self.courseDB.logins):
    ##                 subprocess.call('sh beep.sh &', shell=True)
    ##         except AttributeError:
    ##             pass
    ##     else:
    ##         if len(self.answered) == len(self.responses):
    ##             subprocess.call('sh beep.sh &', shell=True)

    ## def status(self):
    ##     print '\n\nLogins:', len(self.courseDB.logins)
    ##     print 'Responses:', len(self.responses)
    ##     print 'Answers:', len(self.answered)


class QuestionChoice(QuestionBase):
    _stages = ('answer', 'reconsider', 'vote', 'critique', 'self_critique')
    def build_form(self, form, explanation, correctChoice, choices):
        'ask the user to choose an option'
        self._navHTML = self.nav_html(False)
        self.correctAnswer = MultiChoiceResponse(0, self, 0, int(correctChoice))
        self.choices = choices
        self.explanation = explanation
        self._append_to_form(form)
        self._afterURL = self.get_url('vote')

    def _append_to_form(self, form, suffix='', conf=True):
        l = []
        for i,s in enumerate(self.choices):
            l.append((i, '<B>%s</B>. %s' % (letters[i], s)))
        form.append(webui.RadioSelection('choice' + suffix, l))
        if conf:
            add_confidence_choice(form)
        form.append('<br>\n')

    def answer(self, uid, choice=None, confidence=None, monitor=None):
        if missing_params(choice, confidence):
            return _missing_arg_msg
        if uid in self.responses:
            return '''You already answered this question.  When your instructor asks you to, please click here to
        <A HREF="%s">continue</A>.%s''' \
        % (self.get_url('reconsider'), self._navHTML)
        response = MultiChoiceResponse(uid, self, confidence, choice)
        self.isClustered.add(uid) # count this as categorized
        try: # append to its matching category
            self.categories[response].append(response)
            for r in self.categories:
                if r == response:
                    response.prototype = r
        except KeyError: # add this as a new category
            self.categories[response] = [response]
            response.prototype = response
        self.responses[uid] = response
        self.answer_monitor(monitor)
        ## self.alert_if_done(True)
        return '''Thanks for answering! When your instructor asks you to, please click here to
        <A HREF="%s">continue</A>.%s''' \
        % (self.get_url('reconsider'), self._navHTML)
    answer.exposed = True

    def init_vote(self):
        'ensure all choices shown in final vote'
        for i in range(len(self.choices)):
            r = MultiChoiceResponse(i, self, 0, i)
            if r not in self.categories:
                self.categories[r] = []
        self.list_categories(True) # force this to update
        QuestionBase.init_vote(self)

    _afterText = 'the final vote'
        
class QuestionText(QuestionBase):
    def build_form(self, form, correctText,
                   instructions=r'''<br>
    Briefly state your answer to the question
    in the box below.  You may enter latex equations by enclosing them in
    pairs of dollar signs, e.g. \$\$c^2=a^2+b^2\$\$
    or as an inline equation bracketed on the left by a backslash
    followed by open-parenthesis and on the right by a backslash
    followed by close-parenthesis.<br>
    ''', maxview=100):
        'ask the user to enter a text answer'
        self._navHTML = self.nav_html()
        self._correctText = correctText
        self.maxview = maxview
        self.doc.append(webui.Data(instructions))
        self._append_to_form(form)
        self._afterURL = self.get_url('cluster')

    def _append_to_form(self, form, suffix='', conf=True):
        form.append(webui.Textarea('answer' + suffix))
        if conf:
            add_confidence_choice(form)
        form.append('<br>\n')

    def answer(self, uid, answer=None, confidence=None, monitor=None):
        'receive text answer from user'
        if missing_params(answer, confidence) or not answer:
            return _missing_arg_msg
        response = TextResponse(uid, self, confidence, answer)
        self.responses[uid] = response
        self.answer_monitor(monitor)
        ## self.alert_if_done(True)
        return '''Thanks for answering!  When your instructor asks you to, please click here to
        <A HREF="%s">continue</A>.%s''' \
        % (self.get_url('reconsider'), self._navHTML)
    answer.exposed = True

    def add_correct(self):
        self.correctAnswer = TextResponse(0, self, 0, self._correctText)
        self.include_correct()
        self.init_vote()
        return 'Great.  ' + self._gotoVoteHTML

    _afterText = 'categorize your answer'

class QuestionUpload(QuestionBase):
    maxSize = 500000 # don't show images bigger than 500kb
    def build_form(self, form, correctFile, stem='q',
                   imageDir='static/images', maxview=10):
        'ask the user to upload an image file'
        self._navHTML = self.nav_html()
        self._correctFile = correctFile
        self.maxview = maxview
        self.stem = stem
        self.imageDir = imageDir
        self._append_to_form(form)
        self._afterURL = self.get_url('cluster')

    def _append_to_form(self, form, suffix='', conf=True,
                        instructions='''(write your answer on a sheet of paper, take a picture,
        and upload the picture using the button below.  Click here for
        <A HREF="/images/help.html">some helpful instructions</A>).<br>\n'''):
        form.append(instructions)
        form.append(webui.Upload('image' + suffix))
        form.append('''<br>Optionally, you may enter a text answer, e.g. if
        you cannot submit your answer as an image:<br>''')
        form.append(webui.Textarea('answer2' + suffix))
        if conf:
            add_confidence_choice(form)
        form.append('<br>\n')

    def answer(self, uid, image=None, answer2='', confidence=None,
               monitor=None):
        'receive uploaded image file from user'
        if confidence is None or ((not image or not image.file)
                                  and not answer2):
            return _missing_arg_msg
        size = 0
        if image.file:
            studentCode = self.courseDB.students[uid].code
            fname = 'q%d_%d_%s' % (self.id, studentCode, image.filename)
            ifile = open(os.path.join(self.imageDir, fname), 'wb')
            while True:
                data = image.file.read(8192)
                if not data:
                    break
                ifile.write(data)
                size += 8192
            ifile.close()
        else:
            fname = None
        if size > self.maxSize:
            hideMe = '(image too big to display)'
        else:
            hideMe = False
        response = ImageResponse(uid, self, confidence, fname, answer2,
                                 self.imageDir, hideMe)
        self.responses[uid] = response
        self.answer_monitor(monitor)
        ## self.alert_if_done(True)
        return '''Thanks for answering!  When your instructor asks you to, please click here to
        <A HREF="%s">continue</A>.%s''' \
        % (self.get_url('reconsider'), self._navHTML)
    answer.exposed = True

    def add_correct(self):
        self.correctAnswer = ImageResponse(0, self, 0, self._correctFile, '',
                                           self.imageDir)
        self.include_correct()
        self.init_vote()
        return 'Great.  ' + self._gotoVoteHTML

    _afterText = 'categorize your answer'


questionTypes = dict(mc=QuestionChoice,
                     text=QuestionText,
                     image=QuestionUpload)

class QuestionSet(QuestionBase):
    'creates a single form that wraps multiple questions'
    def build_form(self, form, questions):
        self.questions = questions
        self.qsAnswered = set()
        self._navHTML = ''
        for i,q in enumerate(questions):
            form.append('<HR>\n%d. %s<BR>\n' % (i + 1, q.text))
            q._append_to_form(form, '_%d' % i, False)

    def answer(self, monitor=None, **kwargs):
        d = {}
        for attr in kwargs: # sort arguments for each question
            i = int(attr.split('_')[-1])
            d.setdefault(i, []).append(attr)
        for i,q in enumerate(self.questions):
            d2 = {}
            for attr in d.get(i, ()): # copy kwargs for this question
                k = attr.split('_')[0]
                d2[k] = kwargs[attr]
            r = q.answer(confidence=0, **d2)
            if r == _missing_arg_msg: # student left something out...
                return r
        if monitor:
            self.qsAnswered.add(cherrypy.session['UID'])
            monitor.message('answers: %d / %d' % (len(self.qsAnswered),
                                                  len(self.courseDB.logins)))
        return '''Thanks for answering! When your instructor asks you to, please click here to
        <A HREF="/">continue</A>.'''
    answer.exposed = True
            
    def save_responses(self):
        n = 0
        for q in self.questions:
            n += self.courseDB.save_responses(q)
        return '''Saved %d responses total for %d questions.
        Click here to go to the <A HREF='/admin'>PIPS console</A>.''' \
        % (n, len(self.questions))
