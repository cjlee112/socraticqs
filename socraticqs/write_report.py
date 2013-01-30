import coursedb
import sys

def main():
    if len(sys.argv) < 3:
        print 'Usage: %s RSTOUTFILE QUESTIONLIST' % sys.argv[0]
    courseDB = coursedb.CourseDB() # insert students into default DB
    qlist = [int(s) for s in sys.argv[2].split(',')]
    courseDB.write_report(sys.argv[1], qlist)

if __name__ == '__main__':
    main()
