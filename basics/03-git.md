# 3. Git

Git is the input to every pipeline. If you understand commits as a graph, almost nothing in Git is scary.

## Do it

Work in a throwaway repository.

```bash
git init git-lab && cd git-lab
for n in 1 2 3 4 5; do echo "$n" >> file.txt; git add file.txt; git commit -qm "change $n"; done
git log --oneline --graph --all

git switch -c feature HEAD~2
echo feature >> other.txt; git add other.txt; git commit -qm "add feature"
git log --oneline --graph --all

git switch main
git merge --no-edit feature        # Keeps both histories.
git reset --hard HEAD~1            # Undo the merge.
git switch feature
git rebase main                    # Replays the commit with a new hash.
git log --oneline --graph --all
```

Then use `git bisect` to find which commit introduced a bug: pick a line in `file.txt` to be the bug and mark commits good or bad.

## Break it

**Lose work, then recover it.**

```bash
git switch main
git reset --hard HEAD~3
git log --oneline       # The commits look gone.
git reflog              # They are not.
git reset --hard 'HEAD@{1}'
```

**Learn why deleting a secret is not enough.**

```bash
echo "FAKE_TOKEN=abc123" > .env; git add .env; git commit -qm "oops"
git rm -q .env; git commit -qm "remove secret"
ls -a                           # Gone from the working tree.
git log -p --all -S FAKE_TOKEN  # Still in history for everyone who clones.
```

## Explain it

- What does a commit contain, and what does a branch actually point at?
- When would you merge, and when would you rebase? Why not rebase a shared branch?
- What is the difference between `git reset`, `git revert` and `git restore`?
- What is the difference between a lightweight and an annotated tag? Which should a release use?
- A token was pushed to a public repository. What are your steps, in order?

## Done when

You can recover a lost commit with `reflog` without looking it up, and you always answer the last question with "rotate the token first".
