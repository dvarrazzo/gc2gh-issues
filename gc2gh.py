#!/usr/bin/env python
"""Import Google Code issues from Takeout data into GitHub.
"""

import sys
import json
import urllib2

import logging
logger = logging.getLogger()
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s %(message)s')

label_map = {
    'OpSys-Linux': 'Linux',
    'OpSys-OSX': 'OSX',
    'OpSys-OpenBSD': 'OpenBSD',
    'OpSys-Windows': 'Windows',
    'Priority-Low': 'low',
    'Type-Defect': 'bug',
    'Type-Enhancement': 'enhancement',
}

status_map = {
    'Duplicate': 'duplicate',
    'Invalid': 'invalid',
    'WontFix': 'wontfix',
}

class ScriptError(Exception):
    """Controlled exception raised by the script."""

def main():
    opt = parse_cmdline()
    logger.setLevel(opt.loglevel)

    with open(opt.google_data) as f:
        data = json.load(f)

    if 'projects' not in data:
        raise ScriptError("'projects' key not found in input file")

    # find the project in the data
    for d in data['projects']:
        logger.debug("found in projects: %s %s", d.get('kind'), d.get('name'))
        if d.get('name') == opt.google_project:
            issues = dict((i['id'], i) for i in d['issues']['items'])
            logger.info("found %s issues", len(issues))
            if not issues: return
            break
    else:
        raise ScriptError("project not found: %s", opt.google_project)

    # There can be missing issues actually
    for iid in range(min(issues), max(issues) + 1):

        if opt.start_from is not None and iid < opt.start_from:
            logger.debug("issue %s skipped", iid)
            continue

        if opt.finish_at is not None and iid > opt.finish_at:
            logger.debug("issue %s skipped", iid)
            continue

        if iid in issues:
            data = convert_issue(issues[iid])
        else:
            data = make_dummy_issue(iid)

        submit_issue(opt, iid, data)

def convert_issue(oiss):
    logger.debug("converting issue %s", oiss['id'])
    niss = {}
    niss['title'] = oiss['title']
    niss['created_at'] = oiss['published']
    # niss['assignee'] = ?
    # niss['milestone'] = ?
    niss['closed'] = oiss['state'] == 'closed'
    niss['labels'] = nlabels = [
        label_map[s] for s in oiss['labels'] if s in label_map ]
    if oiss['status'] in status_map:
        nlabels.append(status_map[oiss['status']])

    niss['body'] = \
        """Originally submitted by **%s** as **issue %s**:\n\n%s""" % (
            oiss['author']['name'], oiss['id'],
            oiss['comments']['items'][0]['content'])

    ncomms = []
    for ocomm in oiss['comments']['items'][1:]:
        if not ocomm['content']:
            continue
        ncomm = {}
        ncomm['created_at'] = ocomm['published']
        ncomm['body'] = "Comment by **%s**:\n\n%s" % (
            ocomm['author']['name'], ocomm['content'])
        ncomms.append(ncomm)

    return {
        'issue': niss,
        'comments': ncomms,
    }

def make_dummy_issue(iid):
    logger.debug("creating placeholder for issue id %s", iid)
    return {
        'issue': {
            'title': "Placeholder for issue %s" % iid,
            'body': "Issue missing from Google Code",
            'closed': True,
            'labels': ['invalid'],
        },
    }

def submit_issue(opt, iid, data):
    logger.debug("submitting issue %s", iid)
    req = urllib2.Request(
        url="https://api.github.com/repos/%s/%s/import/issues"
            % (opt.github_username, opt.github_project),
        data=json.dumps(data),
        headers={
            'Authorization': 'token %s' % opt.github_token,
            'Accept': 'application/vnd.github.golden-comet-preview+json',}
        )

    try:
        f = urllib2.urlopen(req)
    except urllib2.HTTPError as e:
        logger.error("response code %s", e.code)
        logger.error("response: %s" % e.fp.read())
        raise ScriptError('importing issue %s failed' % iid)
    else:
        logger.debug("response: %s" % f.read())
        logger.info("issue %s submitted: %s", iid, data['issue']['title'])


def parse_cmdline():
    from argparse import ArgumentParser
    parser = ArgumentParser(description=__doc__)

    opt = parser.parse_args()

    # TODO: really parse the command line
    opt.loglevel = logging.DEBUG
    opt.google_data = "GoogleCodeProjectHosting.json"
    opt.google_project = "py-setproctitle"
    opt.github_project = "py-setproctitle-test"
    opt.github_username = "dvarrazzo"
    opt.github_token = "da09cd84307a3602bd958413a8865a2ff66a9927" # Fake :P
    opt.start_from = 8
    opt.finish_at = None

    return opt


if __name__ == '__main__':
    try:
        sys.exit(main())

    except ScriptError, e:
        logger.error("%s", e)
        sys.exit(1)

    except Exception:
        logger.exception("unexpected error")
        sys.exit(1)

    except KeyboardInterrupt:
        logger.info("user interrupt")
        sys.exit(1)
