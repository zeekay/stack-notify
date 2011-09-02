import sys
from collections import OrderedDict

from PyQt4 import QtGui
from PyQt4 import QtCore

import stackexchange as se


API_KEY = 'gbzi3hNc0EKI8Gq-D5zCHA'
so = se.Site(se.StackOverflow, API_KEY)


class StackNotify(QtGui.QSystemTrayIcon):
    tracked = ['django', 'javascript', 'python']
    questions = OrderedDict()
    limit = 10

    title_fmt = 'new question tagged {tags} on so'
    message_fmt = '{title}\nvotes: {votes} answers: {answers}'

    icon_normal = QtGui.QIcon('stackoverflow.png')
    icon_clicked = QtGui.QIcon('stackoverflow-clicked.png')

    def __init__(self):
        super(StackNotify, self).__init__(self.icon_normal, None)
        self.active_icon = icon_normal
        self.activated.connect(self.switch_icon)
        self.menu = QtGui.QMenu(parent)
        self.menu.addSeparator()
        self.menu.addActions([
            QtGui.QAction('Check for new questions', self.menu, triggered=self.update_questions),
            QtGui.QAction('Quit StackNotify', self.menu, triggered=sys.exit),
        ])
        self.setContextMenu(self.menu)
        timer = QtCore.QTimer(self)
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
        action = QtGui.QAction(name, self.menu)
        action.triggered.connect(
            lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(q.url))
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
        icon = self.icon_normal if self.active_icon != self.icon_normal else self.icon_clicked
        self.setIcon(icon)
        self.active_icon = icon

def main():
    app = QtGui.QApplication(sys.argv)
    stacknotify = StackNotify()
    stacknotify.show()
    #stacknotify.update_questions()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()

