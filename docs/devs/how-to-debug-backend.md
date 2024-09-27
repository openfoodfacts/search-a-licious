# How to Debug the backend app

By default, the API runs on uvicorn which use autoreloading and more than one thread, also it does not have a tty. So if you use `pdb.set_trace()` you won't be able to access the console.

To debug the backend app:
* stop API instance: `docker compose stop api`
* add a pdb.set_trace() at the point you want,
* then launch `docker compose run --rm  --use-aliases api uvicorn app.api:app --proxy-headers --host 0.0.0.0 --port 8000 --reload`[^use_aliases]
* go to the url you want to test