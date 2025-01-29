from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

# Mudar para o diretório frontend
os.chdir('frontend')

# Configurar e iniciar o servidor
server_address = ('', 8000)
httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
print('Servidor rodando em http://localhost:8000')
httpd.serve_forever() 