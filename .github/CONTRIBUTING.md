# Contributing

## the basic rule
 
**Nobody pushes straight to `main`.** All changes go through a pull request (PR) that someone else checks.
 
## workflow (one issue = one branch = one PR)
1. **Pick an issue** and assign it to yourself so nobody doubles up.
2. **Make a branch** from an up-to-date `main`:
```bash
   git checkout main
   git pull
   git checkout -b 12-add-login-page
```
3. **Do the work** and commit often with short, clear messages.
4. **Push your branch** when it's ready for review:
```bash
   git push -u origin 12-add-login-page
```
5. **Open a PR** on GitHub. The template will fill in. Write "Closes #12" so the issue closes automatically when it's merged.
6. **Ask a teammate to review.** You can't approve your own PR.
7. **Reviewer tests it and approves** (see below).
8. **Comment on the issue** with what you did (see [comment on your issue](#comment-on-your-issue)).
9. **Merge it**, then delete the branch.

## branch names
 
Use kebab-case, starting with the issue number:
 
- `12-add-login-page`
- `15-fix-navbar-bug`
- `20-update-readme`

## bugs
 
Bugs work the exact same way as features: **one bug = one issue = one branch = one PR.**
 
- Found a bug? Open an issue first. Say what happened, what you expected, and how to repeat it.
- Name the branch like any other: `15-fix-navbar-bug`.
- Found a small, unrelated bug while working on something else? Don't sneak the fix into your current PR. Open a new issue for it (you or someone else can grab it).
- Bug showed up after something was merged? Open a new issue and link the old one (`related to #12`).

## comment on your issue
 
Before you merge, leave a short comment on the issue you're closing so the rest of us know what happened. A few sentences is plenty:
 
- what you changed (and which files, if it helps)
- why you did it that way, if it wasn't obvious
- anything we should watch out for or still need to do later
For bugs, also say **what was causing it**. It saves time if it ever comes back.
 
Example:
 
> Fixed the navbar overlapping the page on mobile. The `z-index` on `.nav` was too low, and I also removed a leftover fixed height in `navbar.css`. Tested on Chrome and Safari mobile sizes. Merged in #16.
 
## reviewing a PR (testing it locally)
 
Don't just read the code. Run it.
 
1. Get the branch:
```bash
   git fetch origin
   git checkout 12-add-login-page
```
2. Install anything new and run the project (`npm install`, `npm start`, etc.).
3. Try out what the PR says it does. Try to break it a little too.
4. Leave comments on the PR if something's off.
5. If it works, click **Review changes → Approve**.
6. Go back to main when you're done:
```bash
   git checkout main
   git pull
```

## merging
 
- Needs **at least 1 approval** and no unresolved comments.
- The **author** merges their own PR after it's approved (so they can fix any last-minute conflicts).
- Use **Squash and merge** to keep `main` history clean.
- Delete the branch after merging.
- Everyone else: `git checkout main && git pull` to stay up to date.
If your PR has merge conflicts, pull `main` into your branch, fix them, and push again:
```bash
git checkout 12-add-login-page
git pull origin main
```