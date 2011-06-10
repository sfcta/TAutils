import re

__all__ = [ 'nodepair_pattern', 'git_commit_pattern', 'tag_num_pattern' ]

nodepair_pattern = re.compile('(\d+)[-,\s]+(\d+)')
git_commit_pattern = re.compile('commit ([0-9a-f]{40}$)')
tag_num_pattern = re.compile('\d+([.]\d+)+')