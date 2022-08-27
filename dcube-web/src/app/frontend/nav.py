from flask_nav import Nav
from dominate import tags
from flask_nav.elements import NavigationItem
from flask_bootstrap.nav import BootstrapRenderer, sha1


class Menustore():
    class __Menustore:
        def __init__(self):
            self.left = {}
            self.right = {}
    instance = None

    def __init__(self):
        if not Menustore.instance:
            Menustore.instance = Menustore.__Menustore()

    def left(self):
        return self.instance.left

    def right(self):
        return self.instance.right


class ExtendedNavbar(NavigationItem):
    def __init__(self, title, root_class='navbar navbar-default', items=[], right_items=[]):
        self.title = title
        self.root_class = root_class
        self.items = items
        self.right_items = right_items


class CustomBootstrapRenderer(BootstrapRenderer):

    def visit_ExtendedNavbar(self, node):
        # create a navbar id that is somewhat fixed, but do not leak any
        # information about memory contents to the outside
        node_id = self.id or sha1(str(id(node)).encode()).hexdigest()

        root = tags.nav() if self.html5 else tags.div(role='navigation')
        root['class'] = node.root_class

        cont = root.add(tags.div(_class='container'))

        # collapse button
        header = cont.add(tags.div(_class='navbar-header'))
        btn = header.add(tags.button())
        btn['type'] = 'button'
        btn['class'] = 'navbar-toggle collapsed'
        btn['data-toggle'] = 'collapse'
        btn['data-target'] = '#' + node_id
        btn['aria-expanded'] = 'false'
        btn['aria-controls'] = 'navbar'

        btn.add(tags.span('Toggle navigation', _class='sr-only'))
        btn.add(tags.span(_class='icon-bar'))
        btn.add(tags.span(_class='icon-bar'))
        btn.add(tags.span(_class='icon-bar'))

        # title may also have a 'get_url()' method, in which case we render
        # a brand-link
        if node.title is not None:
            if ("img" in node.title.attribs):
                header.add(tags.img("brand", _class='navbar-brand',
                                    src=node.title.content))
            elif hasattr(node.title, 'get_url'):
                header.add(tags.a(node.title.text, _class='navbar-brand',
                                  href=node.title.get_url()))
            else:
                header.add(tags.span(node.title, _class='navbar-brand'))

        bar = cont.add(tags.div(
            _class='navbar-collapse collapse',
            id=node_id,
        ))
        bar_list = bar.add(tags.ul(_class='nav navbar-nav'))
        for item in node.items:
            bar_list.add(self.visit(item))

        if node.right_items:
            right_bar_list = bar.add(
                tags.ul(_class='nav navbar-nav navbar-right'))
            for item in node.right_items:
                right_bar_list.add(self.visit(item))

        return root


def init_custom_nav_renderer(app):
    # For some reason, this didn't seem to do anything...
    app.extensions['nav_renderers']['bootstrap'] = (
        __name__, 'CustomBootstrapRenderer')
    # ... but this worked. Weird.
    app.extensions['nav_renderers'][None] = (
        __name__, 'CustomBootstrapRenderer')


nav = Nav()
