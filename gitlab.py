import json
import httplib, urllib
import time, datetime

base_url = ''  # url (and port) of the gitlab server
project_namespace = ''  # gitlab project namespace (user/project_name) Ex: 'user1/test1'
private_token = ''  # this should be for the root account or some sort of import dummy

# Set token for each user so that posts look like they were made by the correct account
# Make sure to use the bitbucket usernames (without @ prefix) as keys, not the potentially new usernames
user_tokens = {
    # 'rawnald-gregory-erickson-ii-bitbucket': 'Gqgdn3b_s6lei_eyrPpi'
}

# For usernames that will differ between bitbucket and gitlab (prefix each username with @)
user_names = {
    # '@rawnald-gregory-erickson-ii-bitbucket': '@rawnald'
}


def get_private_key(user, default=''):
    if user not in user_tokens.keys():
        return default
    return user_tokens[user]


def get_username(username):
    if username not in user_names.keys():
        return username
    return user_names[username]


def get_project_id(project_namespace):
    params = urllib.urlencode({'private_token': private_token})
    headers = {'Content-type': 'application/x-www-form-urlencoded', 'Accept': 'text/plain'}
    url = '/api/v3/projects'
    ret = perform_request('GET', url, params, headers)
    ret = json.loads(ret)
    for project in ret:
        if project['path_with_namespace'] == project_namespace:
            return str(project['id'])
    return None


def parse_timestamp(timestamp, time_zone_offset=-4):
    timestamp = timestamp[:19]  # Remove the milliseconds and timezone
    f = '%Y-%m-%dT%H:%M:%S'
    t = time.strptime(timestamp, f)
    dt = datetime.datetime(*t[:6])
    dt = dt + datetime.timedelta(hours=time_zone_offset)
    return dt.strftime('%m/%d/%y') + ' at ' + dt.strftime('%I:%M %p')


def clean_description(desc):
    desc = desc.encode('ascii', 'ignore')
    p = desc.find('<<cset')
    while p > -1:
        desc = desc[:p] + desc[p:].replace('<<cset', 'See commit:', 1).replace('>>', '', 1)
        p = desc.find('<<cset')
    for user in user_names.keys():
        desc = desc.replace(user, user_names[user])
    return desc


def perform_request(method, url, params, headers):
    conn = httplib.HTTPConnection(base_url)
    conn.request(method, url, params, headers)
    response = conn.getresponse()
    # print response.status, response.reason
    if response.status >= 400:
        print 'method:', method
        print 'url:', url
        print 'params:', params
        print 'headers:', headers
    ret = response.read()
    conn.close()
    return ret


def update_issue_status(comment, project_id, issue_id):
    if 'status_change' not in comment.keys():
        return False

    if comment['status_change'] == 'resolved':
        state = 'close'
    else:
        state = 'reopen'

    pt = get_private_key(comment['user'], private_token)

    params = urllib.urlencode({'state_event': state, 'private_token': pt})
    headers = {'Content-type': 'application/x-www-form-urlencoded', 'Accept': 'text/plain'}
    url = '/api/v3/projects/' + project_id + '/issues/' + issue_id
    perform_request('PUT', url, params, headers)


def post_comment(comment, project_id, issue_id):
    if comment['content'] != None:
        pt = get_private_key(comment['user'])
        description = clean_description(comment['content'])
        post_text = 'Originally posted'
        if pt == '':
            pt = private_token
            post_text = post_text + ' by ' + comment['user']
        
        description = post_text + ' on ' + parse_timestamp(comment['created_on']) + ':\n\n---\n\n' + description

        params = urllib.urlencode({'body': description, 'private_token': pt})
        headers = {'Content-type': 'application/x-www-form-urlencoded', 'Accept': 'text/plain'}
        url = '/api/v3/projects/' + project_id + '/issues/' + issue_id + '/notes'
        perform_request('POST', url, params, headers)
    update_issue_status(comment, project_id, issue_id)


def post_issue(issue, project_id):
    pt = get_private_key(issue['reporter'])
    description = clean_description(issue['content'])
    user_text = ''
    if pt == '':
        pt = private_token
        user_text = ' by ' + issue['reporter']
    
    description = 'Originally reported' + user_text + ' on ' + parse_timestamp(issue['created_on']) + ':\n\n---\n\n' + description

    params = urllib.urlencode({'title': issue['title'], 'description': description, 'private_token': pt})
    headers = {'Content-type': 'application/x-www-form-urlencoded', 'Accept': 'text/plain'}
    url = '/api/v3/projects/' + project_id + '/issues'
    ret = perform_request('POST', url, params, headers)
    ret = json.loads(ret)

    for comment in issue['comments']:
        post_comment(comment, project_id, str(ret['id']))


def main():

    project_id = get_project_id(project_namespace)
    
    if project_id is None:
        print 'ERROR: Could not find project with that namespace'
        return

    with open('db-1.0.json') as data_file:    
        data = json.load(data_file)

    issues = {}
    logs = {}

    for issue in data['issues']:
        issue['comments'] = []
        issues[issue['id']] = issue

    for log in data['logs']:
        logs[log['comment']] = log

    for comment in data['comments']:
        if comment['id'] in logs.keys() and logs[comment['id']]['field'] == 'status':
            comment['status_change'] = logs[comment['id']]['changed_to']
        issues[comment['issue']]['comments'].insert(0, comment)

    for i in xrange(1, len(issues.keys()) + 1):
        post_issue(issues[i], project_id)

if __name__ == '__main__':
    main()
