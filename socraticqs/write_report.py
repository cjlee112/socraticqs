import coursedb
import sys

def main():
    if len(sys.argv) < 2:
        print 'Usage: %s RSTOUTFILE [QUESTIONLIST]' % sys.argv[0]
    courseDB = coursedb.CourseDB() # connect to default DB
    if len(sys.argv) > 2:
        qlist = [int(s) for s in sys.argv[2].split(',')]
    else:
        qlist = None
    courseDB.write_report(sys.argv[1], qlist)

if __name__ == '__main__':
    main()
