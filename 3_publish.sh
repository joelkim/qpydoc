git branch -D gh-pages
git push origin --delete gh-pages
ghp-import -n -p -f -o docs/_site
