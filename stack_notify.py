import argparse
import json
import os
import re
import sys
from collections import OrderedDict

from PyQt4.QtGui import *
from PyQt4.QtCore import *

import lxml.html
import requests

API_URL = 'http://api.stackoverflow.com/1.1/'
ANSWER_PATH = os.path.expanduser('~/.stacknotify/answers')


class Question(dict):
    '''
    Representation of SO Question.
    '''
    def __init__(self, data):
        self.update(data)

    def __getattr__(self, name):
        '''
        Ok just a tiny bit of magic I promise!
        '''
        if name.startswith('_') or name == 'trait_names':
            raise AttributeError
        return self[name]

    @property
    def id(self):
        '''
        Returns id of given question.
        '''
        return self.question_id

    @property
    def url(self):
        '''
        Url to question on stackoverflow.
        '''
        return 'http://stackoverflow.com/questions/%s/' % self.question_id

    @classmethod
    def from_id(cls, id):
        '''
        Static method that returns a new Question from it's id.
        '''
        # Coerce to string. If we're passed a url extract the id from it.
        id = re.search('\d+', str(id)).group()
        res = requests.get(API_URL + 'questions/%s?pagesize=100&sort=creation' % id)
        try:
            return cls(json.loads(res.content)['questions'][0])
        except IndexError:
            raise Exception('Not a valid question')


def recent_questions():
    '''
    Fetches 100 most recent questions, returned as a list.
    '''
    res = requests.get(API_URL + 'questions?pagesize=100&sort=creation')
    return [Question(q) for q in json.loads(res.content)['questions']]


def new_answer(question):
    '''
    Creates directory structure and copies question content into ANSWER_PATH.
    '''
    if not isinstance(question, Question):
        question = Question.from_id(question)

    doc = lxml.html.parse(question.url)
    post = doc.xpath('//div[@id="question"]//div[@class="post-text"]')[0]

    # create directory for answer
    path = os.path.join(ANSWER_PATH, str(question.id))
    if not os.path.exists(path):
        os.makedirs(path)

    # write question
    with open(os.path.join(path, 'question'), 'w') as f:
        f.write('Title: %s\nTags: %s\nUrl: %s\n\nQuestion:' % (question.title, ', '.join(question.tags), question.url))
        f.write(post.text_content().strip())

    # write code examples
    for i, ex in enumerate(post.xpath('//pre'), start=1):
        with open(os.path.join(path, 'code-%d' % i), 'w') as f:
            f.write(ex.text_content())

    print ' '.join([os.path.join(path, f) for f in os.listdir(path)])


def latest_questions(tag):
    '''
    Prints latest questions matching a given tag
    '''
    fmt = '{votes} {answers} {title} {url} {tags}'
    latest = filter(lambda q: tag in q.tags, recent_questions())
    for q in latest:
        votes = str((q.up_vote_count - q.down_vote_count)).zfill(2)
        answers = str(q.answer_count).zfill(2)
        tags = ''.join('[{0}]'.format(tag) for tag in q.tags)
        print fmt.format(votes=votes,
                         answers=answers,
                         title=q.title,
                         url=q.url,
                         tags=tags)
    if not latest:
        print "no recent questions with that tag found"


def get_platform_icons():
    '''
    Returns icons for current platform.
    '''
    icons = {
        'darwin': ('stackoverflow-mac.png', 'stackoverflow-clicked-mac.png'),
        'linux2': ('stackoverflow.png', 'stackoverflow-clicked.png')
    }
    basedir = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'icons')
    return [os.path.join(basedir, icon) for icon in icons.get(sys.platform, icons['linux2'])]

class StackNotify(QSystemTrayIcon):
    '''
    Systray application that notifies when new questions are added on Stackoverflow.
    '''
    questions = OrderedDict()
    limit = 10

    title_fmt = 'new question tagged {tags} on so'
    message_fmt = '{title}\nvotes: {votes} answers: {answers}'

    def __init__(self, tracked, parent=None):
        self.tracked = tracked
        normal_icon, clicked_icon = get_platform_icons()
        icon = QIcon(QPixmap(normal_icon))
        icon.addPixmap(QPixmap(clicked_icon), QIcon.Selected)
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
        title = self.title_fmt.format(tags=', '.join(q.tags))
        message = self.message_fmt.format(votes=votes, title=q.title, answers=q.answer_count)
        self.showMessage(title, message)

    def add_question(self, q):
        name = '{title} {votes} / {answers}'.format(
            title=q.title,
            votes=q.up_vote_count - q.down_vote_count,
            answers=q.answer_count,
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
        for q in recent_questions():
            if self.tracked and not set(self.tracked) & set(q.tags):
                continue
            if q.id not in self.questions:
                self.add_question(q)
                self.notify(q)
        for i,k in enumerate(reversed(self.questions)):
            if i > self.limit:
                self.remove_question(q)


def run_stacknotify(tracked):
    '''
    Runs the systray notification app.
    '''
    app = QApplication(sys.argv)
    stacknotify = StackNotify(tracked)
    stacknotify.show()
    stacknotify.update_questions()
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
        run_stacknotify(args.track)
