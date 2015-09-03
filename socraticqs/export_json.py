import json
import codecs
import coursedb
import random

def generate_dict(rows, columns):
    'generate dict containing non-null attrs for each row'
    for row in rows:
        d = {}
        for i,field in enumerate(columns):
            if row[i] is not None and row[i] != '':
                d[field] = row[i]
        yield d

def anonymize_responses(questions):
    'remove uid from responses and student_errors, replace with random username'
    anon = {}
    for q in questions:
        for r in q['responses']:
            uid = r['uid']
            try:
                username = anon[uid]
            except KeyError:
                username = anon[uid] = 'user%d' % random.randint(0, 1000000000)
            del r['uid']
            r['username'] = username
            for se in r['errors']:
                del se['uid']
    return anon.values()
        
def get_orct_data(dbconn, anonymize=True,
                  selfevals=('correct', 'close', 'different')):
    'get list of question dicts w/ associated responses etc.'
    dbconn.c.execute('select * from questions') # get all questions
    questions = {}
    for q in generate_dict(dbconn.c.fetchall(),
                           coursedb.CourseDB._questionSchema):
        q['responses'] = [] # default: no responses
        q['errors'] = [] # default: no error models
        questions[q['question_id']] = q
    dbconn.c.execute('select * from responses') # add response to each question
    for r in generate_dict(dbconn.c.fetchall(),
                           coursedb.CourseDB._responseSchema):
        if r.get('reasons', 'SKIP') in selfevals:
            r['selfeval'] = r['reasons']
        r['errors'] = [] # default: no error models
        q = questions[r['question_id']]
        q['responses'].append(r)
    errors = {}
    dbconn.c.execute('select * from error_models') # add EM to each question
    for em in generate_dict(dbconn.c.fetchall(),
                           coursedb.CourseDB._errorSchema):
        q = questions[em['question_id']]
        q['errors'].append(em)
        errors[em['error_id']] = em
    dbconn.c.execute('select * from student_errors') # add SE to each response
    n = 0
    for se in generate_dict(dbconn.c.fetchall(),
                           coursedb.CourseDB._studentErrorSchema):
        em = errors[se['error_id']]
        q = questions[em['question_id']]
        for r in q['responses']:
            if r['uid'] == se['uid']: # same student
                r['errors'].append(se)
                n += 1
                break
    print 'saved %d student errors' % n
    if anonymize:
        usernames = anonymize_responses(questions.values())
    else:
        usernames = ()
    dates = {} # group questions by date
    for q in questions.values():
        dates.setdefault(q['date_added'], []).append(q)
    for l in dates.values(): # sort each list by primary key
        l.sort(lambda x,y:cmp(x['question_id'], y['question_id']))
    datelist = list(dates)
    datelist.sort()
    qlist = [dates[date] for date in datelist]
    return qlist, usernames

def export_orct_data(dbfile='course.db', **kwargs):
    'save ORCT response data in JSON format'
    dbconn = coursedb.DBConnection(dbfile)
    outfile = dbfile + '.json'
    print 'writing', outfile
    questions, usernames = get_orct_data(dbconn, **kwargs)
    data = dict(questions=questions, usernames=usernames)
    with codecs.open(outfile, 'w', encoding='utf-8') as ofile:
        json.dump(data, ofile)
    dbconn.close()
    
if __name__ == '__main__':
    import sys
    export_orct_data(*sys.argv[1:])
