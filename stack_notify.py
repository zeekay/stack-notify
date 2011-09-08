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


class StackNotify(QSystemTrayIcon):
    tracked = ['django', 'javascript', 'python']
    questions = OrderedDict()
    limit = 10

    title_fmt = 'new question tagged {tags} on so'
    message_fmt = '{title}\nvotes: {votes} answers: {answers}'

    icons = ['stackoverflow.png', 'stackoverflow-clicked.png']

    def __init__(self, parent=None):
        super(StackNotify, self).__init__(QIcon(self.icons[0]), parent)
        self.menu = QMenu(parent)
        self.menu.addSeparator()
        self.menu.addActions([
            QAction('Check for new questions', self.menu, triggered=self.update_questions),
            QAction('Quit StackNotify', self.menu, triggered=sys.exit),
        ])
        self.menu.aboutToShow.connect(self.switch_icon)
        self.menu.aboutToHide.connect(self.switch_icon)
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

    def rm_question(self, q):
        self.menu.removeAction(self.questions[q.id]['action'])
        del self.questions[q.id]

    def update_questions(self):
        qs = so.questions()
        latest = sorted(qs.items, key=lambda q: q.creation_date, reverse=True)
        for q in latest:
            if filter(lambda tag: tag in self.tracked, q.tags) and q.id not in self.questions:
                self.add_question(q)
                self.notify(q)
        for i,k in enumerate(reversed(self.questions)):
            if i > self.limit:
                self.remove_question(q)

    def switch_icon(self):
        self.icons.reverse()
        self.setIcon(QIcon(self.icons[0]))

def main():
    app = QApplication(sys.argv)
    stacknotify = StackNotify()
    stacknotify.show()
    #stacknotify.update_questions()
    sys.exit(app.exec_())

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--question', metavar="question or id", required=False)

    args = parser.parse_args()

    if args.question:
        new_answer(args.question)
    else:
        main()
