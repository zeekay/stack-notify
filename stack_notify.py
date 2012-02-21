import argparse, os, re, sys
from collections import OrderedDict

from PyQt4.QtGui import *
from PyQt4.QtCore import *

import stackexchange as se
import lxml.html

ANSWER_PATH = '/Volumes/Data/zk/Code/so/'
API_KEY = 'gbzi3hNc0EKI8Gq-D5zCHA'

so = se.Site(se.StackOverflow, API_KEY)

def new_answer(question):
    """Creates directory structure and copies question content into ANSWER_PATH"""
    if not isinstance(question, se.Question):
        try:
            # assume string
            id = re.search('\d+', question).group()
            question = so.question(id)
        except TypeError:
            # possibly int?
            question = so.question(question)

    doc = lxml.html.parse(question.url)
    post = doc.xpath('//div[@id="question"]//div[@class="post-text"]')[0]

    # create directory for answer
    path = os.path.join(ANSWER_PATH, str(question.id))
    if not os.path.exists(path):
        os.mkdir(path)

    # write question
    with open(os.path.join(path, 'question'), 'w') as f:
        f.write('Title: %s\nTags: %s\nUrl: %s\n\nQuestion:' % (question.title, ', '.join(question.tags), question.url))
        f.write(post.text_content().strip())

    # write code examples
    for i, ex in enumerate(post.xpath('//pre'), start=1):
        with open(os.path.join(path, '-'.join(ex, str(i)))) as f:
            f.write(ex)


def latest_questions(tag):
    fmt = '{votes} {answers} {title} {url} {tags}'
    qs = so.questions()
    latest = sorted((q for q in qs.items if tag in q.tags), key=lambda q: q.creation_date, reverse=True)
    for q in latest:
        votes = str((q.up_vote_count - q.down_vote_count)).zfill(2)
        answers = str(len(q.answers)).zfill(2)
        tags = ''.join('[{0}]'.format(tag) for tag in q.tags)
        print fmt.format(votes=votes,
                         answers=answers,
                         title=q.title,
                         url=q.url,
                         tags=tags)
    if not latest:
        print "no recent questions with that tag found"

class StackNotify(QSystemTrayIcon):
    questions = OrderedDict()
    limit = 10

    title_fmt = 'new question tagged {tags} on so'
    message_fmt = '{title}\nvotes: {votes} answers: {answers}'

    def __init__(self, tracked, parent=None):
        # tags we want to track
        self.tracked = tracked

        # set default image to black if on OSX, else use white for both icons
        # since I have a black xmobar in linux :3
        if sys.platform == 'linux2':
            icon = QIcon(QPixmap('stackoverflow-clicked.png'))
        else:
            icon = QIcon(QPixmap('stackoverflow.png'))
        icon.addPixmap(QPixmap('stackoverflow-clicked.png'), QIcon.Selected)
        super(StackNotify, self).__init__(icon, parent)
        self.menu = QMenu(parent)
        self.menu.addSeparator()
        self.menu.addActions([
            QAction('Check for new questions', self.menu, triggered=self.update_questions),
            QAction('Quit StackNotify', self.menu, triggered=sys.exit),
        ])
        self.setContextMenu(self.menu)
        timer = QTimer(self)
        timer.timeout.connect(self.update_questions)
        timer.start(1000*60)

    def notify(self, q):
        votes = q.up_vote_count - q.down_vote_count
        num_answers = len(q.answers)
        title = self.title_fmt.format(tags=', '.join(q.tags))
        message = self.message_fmt.format(votes=votes, title=q.title, answers=num_answers)
        self.showMessage(title, message)

    def add_question(self, q):
        name = '{title} {votes} / {answers}'.format(
            title=q.title,
            votes=q.up_vote_count - q.down_vote_count,
            answers=len(q.answers),
        )
        action = QAction(name, self.menu)
        action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl(q.url))
        )
        self.questions[q.id] = {
            'action': action,
            'question': q,
        }
        self.menu.insertAction(self.menu.actions()[0], action)

    def remove_question(self, q):
        self.menu.removeAction(self.questions[q.id]['action'])
        del self.questions[q.id]

    def update_questions(self):
        qs = so.questions()
        latest = sorted(qs.items, key=lambda q: q.creation_date, reverse=True)
        for q in latest:
            if self.tracked and not filter(lambda tag: tag in self.tracked, q.tags):
                continue
            if q.id not in self.questions:
                self.add_question(q)
                self.notify(q)
        for i,k in enumerate(reversed(self.questions)):
            if i > self.limit:
                self.remove_question(q)


def main(tracked):
    app = QApplication(sys.argv)
    stacknotify = StackNotify(tracked)
    stacknotify.show()
    #stacknotify.update_questions()
    sys.exit(app.exec_())

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--answer', metavar="create answer for question", required=False)
    parser.add_argument('--latest', metavar="latest questions for a particular tag", required=False)
    parser.add_argument('--track', metavar='tags to track', nargs='+', default=(), required=False)
    args = parser.parse_args()

    if args.answer:
        new_answer(args.answer)
    elif args.latest:
        latest_questions(args.latest)
    else:
        print args.track
        main(args.track)
