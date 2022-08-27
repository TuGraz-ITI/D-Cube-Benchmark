from app import create_app
#from werkzeug.contrib.profiler import ProfilerMiddleware

app=create_app()
#app.wsgi_app = ProfilerMiddleware(app.wsgi_app)
#app.run(debug=False,host="0.0.0.0")
