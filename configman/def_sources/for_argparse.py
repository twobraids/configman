# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is configman
#
# The Initial Developer of the Original Code is
# Mozilla Foundation
# Portions created by the Initial Developer are Copyright (C) 2011
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#    K Lars Lohn, lars@mozilla.com
#    Peter Bengtsson, peterbe@mozilla.com
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

# this is a stub for future implementation

try:
    import argparse
    import inspect

    from .. import namespace

    # horrors
    def find_action_name_by_value(registry, target):
        target_type = type(target)
        for key, value in registry['action'].iteritems():
            if value is target_type:
                if key is None:
                    return 'store'
                return key
        return None

    def get_args_and_values(an_action):
        args = inspect.getargspec(an_action.__class__.__init__).args
        print "ttttttt", args
        kwargs = dict(
            (an_attr, getattr(an_action, an_attr))
            for an_attr in args if an_attr not in ('self', 'required')
        )
        return kwargs


    def setup_definitions(source, destination):
        # assume that source is of type argparse
        for an_action in source._optionals._actions:
            if an_action.default != argparse.SUPPRESS:
                the_class = an_action.__class__
                print "class:", the_class.__name__, an_action.dest
                kwargs = get_args_and_values(an_action)
                kwargs['action'] = find_action_name_by_value(
                    source._optionals._registries,
                    the_class
                )
                if kwargs['const'] is not None:
                    kwargs['nargs'] = '?'
                destination.add_option(
                    name = an_action.dest,
                    default = an_action.default,
                    from_string_converter = an_action.type,
                    doc = an_action.help,
                    foreign_data=(argparse, kwargs)
                )
            else:
                print "argparse: skipping", type(an_action), an_action.dest

    type_to_setup_association = {argparse.ArgumentParser: setup_definitions}

except ImportError:

    type_to_setup_association = {}
