from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
from functools import wraps
import csv, io, os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'tintacontrol-secret-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/tintacontrol'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ─────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    nome = db.Column(db.String(100))
    perfil = db.Column(db.String(20), default='operador')  # admin, operador
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)


class AuditLog(db.Model):
    __tablename__ = 'audit_log'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    username = db.Column(db.String(50))  # guardamos mesmo se usuário for deletado
    acao = db.Column(db.String(100), nullable=False)
    detalhe = db.Column(db.Text)
    ip = db.Column(db.String(45))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'acao': self.acao,
            'detalhe': self.detalhe,
            'ip': self.ip,
            'criado_em': self.criado_em.strftime('%d/%m/%Y %H:%M:%S'),
        }


def registrar_log(acao, detalhe=None):
    """Helper para gravar auditoria de qualquer rota."""
    try:
        log = AuditLog(
            usuario_id=session.get('user_id'),
            username=session.get('username', 'desconhecido'),
            acao=acao,
            detalhe=detalhe,
            ip=request.remote_addr,
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        pass  # nunca deixar o log quebrar a operação principal


class Produto(db.Model):
    __tablename__ = 'produtos'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    nome = db.Column(db.String(150), nullable=False)
    categoria = db.Column(db.String(100))
    unidade = db.Column(db.String(10), default='UN')
    descricao = db.Column(db.Text)
    qtd_estoque = db.Column(db.Numeric(10, 3), default=0)
    custo_unitario = db.Column(db.Numeric(10, 2), default=0)
    markup = db.Column(db.Numeric(5, 2), default=0)
    preco_venda = db.Column(db.Numeric(10, 2), default=0)
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'codigo': self.codigo, 'nome': self.nome,
            'categoria': self.categoria, 'unidade': self.unidade,
            'descricao': self.descricao,
            'qtd_estoque': float(self.qtd_estoque or 0),
            'custo_unitario': float(self.custo_unitario or 0),
            'markup': float(self.markup or 0),
            'preco_venda': float(self.preco_venda or 0),
        }


class EntradaEstoque(db.Model):
    __tablename__ = 'entradas_estoque'
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True, nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    quantidade = db.Column(db.Numeric(10, 3), nullable=False)
    valor_total_nf = db.Column(db.Numeric(10, 2))
    custo_unitario = db.Column(db.Numeric(10, 2))
    markup = db.Column(db.Numeric(5, 2))
    preco_venda = db.Column(db.Numeric(10, 2))
    observacao = db.Column(db.Text)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    produto = db.relationship('Produto', backref='entradas')
    usuario = db.relationship('Usuario')

    def to_dict(self):
        return {
            'id': self.id, 'numero': self.numero,
            'produto': self.produto.nome if self.produto else '',
            'produto_codigo': self.produto.codigo if self.produto else '',
            'quantidade': float(self.quantidade or 0),
            'valor_total_nf': float(self.valor_total_nf or 0),
            'custo_unitario': float(self.custo_unitario or 0),
            'markup': float(self.markup or 0),
            'preco_venda': float(self.preco_venda or 0),
            'observacao': self.observacao or '',
            'criado_em': self.criado_em.strftime('%d/%m/%Y, %H:%M') if self.criado_em else '',
        }


class SaidaEstoque(db.Model):
    __tablename__ = 'saidas_estoque'
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True, nullable=False)
    motivo = db.Column(db.String(100))
    observacao = db.Column(db.Text)
    valor_total = db.Column(db.Numeric(10, 2), default=0)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    usuario = db.relationship('Usuario')
    itens = db.relationship('SaidaEstoqueItem', backref='saida', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id, 'numero': self.numero, 'motivo': self.motivo,
            'observacao': self.observacao or '',
            'valor_total': float(self.valor_total or 0),
            'qtd_itens': len(self.itens),
            'usuario': self.usuario.nome if self.usuario else '',
            'criado_em': self.criado_em.strftime('%d/%m/%Y, %H:%M') if self.criado_em else '',
            'itens': [i.to_dict() for i in self.itens],
        }


class SaidaEstoqueItem(db.Model):
    __tablename__ = 'saidas_estoque_itens'
    id = db.Column(db.Integer, primary_key=True)
    saida_id = db.Column(db.Integer, db.ForeignKey('saidas_estoque.id'), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    quantidade = db.Column(db.Numeric(10, 3), nullable=False)
    preco_unitario = db.Column(db.Numeric(10, 2))
    total = db.Column(db.Numeric(10, 2))
    produto = db.relationship('Produto')

    def to_dict(self):
        return {
            'id': self.id,
            'produto_id': self.produto_id,
            'produto': self.produto.nome if self.produto else '',
            'codigo': self.produto.codigo if self.produto else '',
            'unidade': self.produto.unidade if self.produto else '',
            'quantidade': float(self.quantidade or 0),
            'preco_unitario': float(self.preco_unitario or 0),
            'total': float(self.total or 0),
        }


class Pedido(db.Model):
    __tablename__ = 'pedidos'
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True, nullable=False)
    status = db.Column(db.String(20), default='aberto')  # aberto, cancelado, faturado
    valor_total = db.Column(db.Numeric(10, 2), default=0)
    motivo_cancelamento = db.Column(db.Text)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    usuario = db.relationship('Usuario')
    itens = db.relationship('PedidoItem', backref='pedido', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id, 'numero': self.numero, 'status': self.status,
            'valor_total': float(self.valor_total or 0),
            'criado_em': self.criado_em.strftime('%d/%m/%Y, %H:%M') if self.criado_em else '',
            'itens': [i.to_dict() for i in self.itens],
        }


class PedidoItem(db.Model):
    __tablename__ = 'pedidos_itens'
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    quantidade = db.Column(db.Numeric(10, 3), nullable=False)
    preco_unitario = db.Column(db.Numeric(10, 2))
    total = db.Column(db.Numeric(10, 2))
    produto = db.relationship('Produto')

    def to_dict(self):
        return {
            'id': self.id, 'produto_id': self.produto_id,
            'produto': self.produto.nome if self.produto else '',
            'codigo': self.produto.codigo if self.produto else '',
            'unidade': self.produto.unidade if self.produto else '',
            'quantidade': float(self.quantidade or 0),
            'preco_unitario': float(self.preco_unitario or 0),
            'total': float(self.total or 0),
        }


class Orcamento(db.Model):
    __tablename__ = 'orcamentos'
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True, nullable=False)
    status = db.Column(db.String(20), default='ativo')
    valor_total = db.Column(db.Numeric(10, 2), default=0)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    usuario = db.relationship('Usuario')
    itens = db.relationship('OrcamentoItem', backref='orcamento', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id, 'numero': self.numero, 'status': self.status,
            'valor_total': float(self.valor_total or 0),
            'criado_em': self.criado_em.strftime('%d/%m/%Y, %H:%M') if self.criado_em else '',
            'itens': [i.to_dict() for i in self.itens],
        }


class OrcamentoItem(db.Model):
    __tablename__ = 'orcamentos_itens'
    id = db.Column(db.Integer, primary_key=True)
    orcamento_id = db.Column(db.Integer, db.ForeignKey('orcamentos.id'), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    quantidade = db.Column(db.Numeric(10, 3), nullable=False)
    preco_unitario = db.Column(db.Numeric(10, 2))
    total = db.Column(db.Numeric(10, 2))
    produto = db.relationship('Produto')

    def to_dict(self):
        return {
            'id': self.id, 'produto_id': self.produto_id,
            'produto': self.produto.nome if self.produto else '',
            'codigo': self.produto.codigo if self.produto else '',
            'unidade': self.produto.unidade if self.produto else '',
            'quantidade': float(self.quantidade or 0),
            'preco_unitario': float(self.preco_unitario or 0),
            'total': float(self.total or 0),
        }


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('perfil') != 'admin':
            return jsonify({'error': 'Acesso restrito a administradores.'}), 403
        return f(*args, **kwargs)
    return decorated


def next_code(prefix, model, field):
    last = db.session.query(model).order_by(model.id.desc()).first()
    num = (last.id + 1) if last else 1
    return f"{prefix}{num:06d}"


# ─────────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────────

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        data = request.get_json() or request.form
        user = Usuario.query.filter_by(username=data.get('username'), ativo=True).first()
        if user and user.check_senha(data.get('senha', '')):
            session['user_id'] = user.id
            session['username'] = user.username
            session['nome'] = user.nome or user.username
            session['perfil'] = user.perfil
            registrar_log('LOGIN', f'Usuário {user.username} fez login')
            if request.is_json:
                return jsonify({'ok': True})
            return redirect(url_for('dashboard'))
        error = 'Usuário ou senha inválidos.'
        registrar_log('LOGIN_FALHOU', f'Tentativa de login com usuário "{data.get("username")}"')
        if request.is_json:
            return jsonify({'ok': False, 'error': error}), 401
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    registrar_log('LOGOUT', f'Usuário {session.get("username")} encerrou sessão')
    session.clear()
    return redirect(url_for('login'))


# ─────────────────────────────────────────────
# PAGE ROUTES
# ─────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')


@app.route('/produtos')
@login_required
def produtos():
    return render_template('produtos.html')


@app.route('/estoque/entrada')
@login_required
def estoque_entrada():
    return render_template('estoque_entrada.html')


@app.route('/estoque/saida')
@login_required
def estoque_saida():
    return render_template('estoque_saida.html')


@app.route('/estoque/relatorio')
@login_required
def estoque_relatorio():
    return render_template('estoque_relatorio.html')


@app.route('/vendas/pedido')
@login_required
def vendas_pedido():
    return render_template('vendas_pedido.html')


@app.route('/vendas/cancelamento')
@login_required
def vendas_cancelamento():
    return render_template('vendas_cancelamento.html')


@app.route('/faturamento/orcamento')
@login_required
def faturamento_orcamento():
    return render_template('faturamento_orcamento.html')


@app.route('/faturamento/nfe')
@login_required
def faturamento_nfe():
    return render_template('faturamento_nfe.html')


@app.route('/banco-de-dados')
@login_required
def banco_dados():
    return render_template('banco_dados.html')


# ─────────────────────────────────────────────
# API – DASHBOARD
# ─────────────────────────────────────────────

@app.route('/api/dashboard')
@login_required
def api_dashboard():
    from sqlalchemy import func
    total_produtos = Produto.query.filter_by(ativo=True).count()
    pedidos_abertos = Pedido.query.filter_by(status='aberto').count()
    valor_estoque = db.session.query(
        func.sum(Produto.qtd_estoque * Produto.preco_venda)
    ).filter_by(ativo=True).scalar() or 0

    hoje = date.today()
    pedidos_hoje = Pedido.query.filter(
        db.func.date(Pedido.criado_em) == hoje
    ).count()

    movimentos = Pedido.query.order_by(Pedido.criado_em.desc()).limit(10).all()
    return jsonify({
        'total_produtos': total_produtos,
        'pedidos_abertos': pedidos_abertos,
        'valor_estoque': float(valor_estoque),
        'pedidos_hoje': pedidos_hoje,
        'movimentos': [p.to_dict() for p in movimentos],
    })


# ─────────────────────────────────────────────
# API – PRODUTOS
# ─────────────────────────────────────────────

@app.route('/api/produtos', methods=['GET'])
@login_required
def api_produtos():
    q = request.args.get('q', '').strip()
    query = Produto.query.filter_by(ativo=True)
    if q:
        query = query.filter(
            db.or_(Produto.nome.ilike(f'%{q}%'), Produto.codigo.ilike(f'%{q}%'))
        )
    return jsonify([p.to_dict() for p in query.order_by(Produto.nome).all()])


@app.route('/api/produtos', methods=['POST'])
@login_required
def api_produto_criar():
    d = request.get_json()
    codigo = next_code('PROD', Produto, 'codigo')
    p = Produto(
        codigo=codigo, nome=d['nome'],
        categoria=d.get('categoria', ''), unidade=d.get('unidade', 'UN'),
        descricao=d.get('descricao', ''),
    )
    db.session.add(p)
    db.session.commit()
    registrar_log('PRODUTO_CRIADO', f'Produto {p.codigo} – {p.nome}')
    return jsonify(p.to_dict()), 201


@app.route('/api/produtos/<int:pid>', methods=['PUT'])
@login_required
def api_produto_editar(pid):
    p = Produto.query.get_or_404(pid)
    d = request.get_json()
    for k in ('nome', 'categoria', 'unidade', 'descricao'):
        if k in d:
            setattr(p, k, d[k])
    db.session.commit()
    registrar_log('PRODUTO_EDITADO', f'Produto {p.codigo} – {p.nome}')
    return jsonify(p.to_dict())


@app.route('/api/produtos/<int:pid>', methods=['DELETE'])
@login_required
def api_produto_deletar(pid):
    p = Produto.query.get_or_404(pid)
    p.ativo = False
    db.session.commit()
    registrar_log('PRODUTO_DESATIVADO', f'Produto {p.codigo} – {p.nome}')
    return jsonify({'ok': True})


# ─────────────────────────────────────────────
# API – ENTRADA ESTOQUE
# ─────────────────────────────────────────────

@app.route('/api/estoque/entradas', methods=['GET'])
@login_required
def api_entradas():
    entradas = EntradaEstoque.query.order_by(EntradaEstoque.id.desc()).limit(50).all()
    return jsonify([e.to_dict() for e in entradas])


@app.route('/api/estoque/entrada', methods=['POST'])
@login_required
def api_entrada_criar():
    d = request.get_json()
    produto = Produto.query.get_or_404(d['produto_id'])

    qtd = float(d['quantidade'])
    val_nf = float(d.get('valor_total_nf', 0))
    markup = float(d.get('markup', 0))
    custo_unit = val_nf / qtd if qtd > 0 else 0
    preco_venda = custo_unit * (1 + markup / 100)

    entrada = EntradaEstoque(
        numero=next_code('ENT', EntradaEstoque, 'numero'),
        produto_id=produto.id,
        quantidade=qtd, valor_total_nf=val_nf,
        custo_unitario=custo_unit, markup=markup,
        preco_venda=preco_venda,
        observacao=d.get('observacao', ''),
        usuario_id=session['user_id'],
    )
    db.session.add(entrada)

    # atualiza estoque
    produto.qtd_estoque = float(produto.qtd_estoque or 0) + qtd
    produto.custo_unitario = custo_unit
    produto.markup = markup
    produto.preco_venda = preco_venda
    db.session.commit()
    registrar_log('ENTRADA_ESTOQUE', f'{entrada.numero} – {produto.nome} – Qtd: {qtd}')
    return jsonify(entrada.to_dict()), 201


# ─────────────────────────────────────────────
# API – SAÍDA ESTOQUE
# ─────────────────────────────────────────────

@app.route('/api/estoque/saidas', methods=['GET'])
@login_required
def api_saidas():
    saidas = SaidaEstoque.query.order_by(SaidaEstoque.id.desc()).limit(50).all()
    return jsonify([s.to_dict() for s in saidas])


@app.route('/api/estoque/saida', methods=['POST'])
@login_required
def api_saida_criar():
    d = request.get_json()
    saida = SaidaEstoque(
        numero=next_code('SAI', SaidaEstoque, 'numero'),
        motivo=d.get('motivo', 'Ajuste de Estoque'),
        observacao=d.get('observacao', ''),
        usuario_id=session['user_id'],
    )
    db.session.add(saida)
    total = 0
    for item in d.get('itens', []):
        produto = Produto.query.get_or_404(item['produto_id'])
        qtd = float(item['quantidade'])
        preco = float(produto.preco_venda or 0)
        subtotal = qtd * preco
        total += subtotal
        si = SaidaEstoqueItem(
            saida=saida, produto_id=produto.id,
            quantidade=qtd, preco_unitario=preco, total=subtotal
        )
        db.session.add(si)
        produto.qtd_estoque = max(0, float(produto.qtd_estoque or 0) - qtd)
    saida.valor_total = total
    db.session.commit()
    registrar_log('SAIDA_ESTOQUE', f'{saida.numero} – Motivo: {saida.motivo} – Total: R${total:.2f}')
    return jsonify(saida.to_dict()), 201


# ─────────────────────────────────────────────
# API – RELATÓRIO / CSV
# ─────────────────────────────────────────────

@app.route('/api/estoque/relatorio')
@login_required
def api_relatorio():
    produtos = Produto.query.filter_by(ativo=True).order_by(Produto.nome).all()
    from sqlalchemy import func
    total = db.session.query(
        func.sum(Produto.qtd_estoque * Produto.preco_venda)
    ).filter_by(ativo=True).scalar() or 0
    return jsonify({'produtos': [p.to_dict() for p in produtos], 'total_estoque': float(total)})


@app.route('/api/estoque/exportar-csv')
@login_required
def api_exportar_csv():
    produtos = Produto.query.filter_by(ativo=True).order_by(Produto.nome).all()
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(['Código', 'Nome', 'Unidade', 'Categoria', 'Qtd Estoque',
                'Custo Unit.', 'Markup %', 'Venda Unit.', 'Total Estoque'])
    for p in produtos:
        w.writerow([
            p.codigo, p.nome, p.unidade, p.categoria or '',
            float(p.qtd_estoque or 0), float(p.custo_unitario or 0),
            float(p.markup or 0), float(p.preco_venda or 0),
            float((p.qtd_estoque or 0) * (p.preco_venda or 0)),
        ])
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'estoque_{date.today()}.csv'
    )


# ─────────────────────────────────────────────
# API – PEDIDOS
# ─────────────────────────────────────────────

@app.route('/api/pedidos', methods=['GET'])
@login_required
def api_pedidos():
    pedidos = Pedido.query.order_by(Pedido.id.desc()).limit(50).all()
    return jsonify([p.to_dict() for p in pedidos])


@app.route('/api/pedidos/<numero>', methods=['GET'])
@login_required
def api_pedido_get(numero):
    p = Pedido.query.filter_by(numero=numero).first()
    if not p:
        return jsonify({'error': 'Pedido não encontrado'}), 404
    return jsonify(p.to_dict())


@app.route('/api/pedidos', methods=['POST'])
@login_required
def api_pedido_criar():
    d = request.get_json()
    pedido = Pedido(
        numero=next_code('PED', Pedido, 'numero'),
        usuario_id=session['user_id'],
    )
    db.session.add(pedido)
    total = 0
    for item in d.get('itens', []):
        produto = Produto.query.get_or_404(item['produto_id'])
        qtd = float(item['quantidade'])
        preco = float(produto.preco_venda or 0)
        subtotal = qtd * preco
        total += subtotal
        pi = PedidoItem(
            pedido=pedido, produto_id=produto.id,
            quantidade=qtd, preco_unitario=preco, total=subtotal
        )
        db.session.add(pi)
        produto.qtd_estoque = max(0, float(produto.qtd_estoque or 0) - qtd)
    pedido.valor_total = total
    db.session.commit()
    registrar_log('PEDIDO_CRIADO', f'{pedido.numero} – Total: R${total:.2f}')
    return jsonify(pedido.to_dict()), 201


@app.route('/api/pedidos/<numero>/cancelar', methods=['POST'])
@login_required
def api_pedido_cancelar(numero):
    p = Pedido.query.filter_by(numero=numero).first()
    if not p:
        return jsonify({'error': 'Pedido não encontrado'}), 404
    if p.status == 'cancelado':
        return jsonify({'error': 'Pedido já cancelado'}), 400
    # devolve estoque
    for item in p.itens:
        produto = Produto.query.get(item.produto_id)
        if produto:
            produto.qtd_estoque = float(produto.qtd_estoque or 0) + float(item.quantidade or 0)
    p.status = 'cancelado'
    db.session.commit()
    registrar_log('PEDIDO_CANCELADO', f'Pedido {p.numero}')
    return jsonify({'ok': True, 'pedido': p.to_dict()})


@app.route('/api/pedidos/<numero>/faturar', methods=['POST'])
@login_required
def api_pedido_faturar(numero):
    p = Pedido.query.filter_by(numero=numero).first()
    if not p:
        return jsonify({'error': 'Pedido não encontrado'}), 404
    if p.status != 'aberto':
        return jsonify({'error': f'Pedido com status "{p.status}" não pode ser faturado'}), 400
    p.status = 'faturado'
    db.session.commit()
    registrar_log('PEDIDO_FATURADO', f'Pedido {p.numero}')
    return jsonify({'ok': True, 'pedido': p.to_dict()})


# ─────────────────────────────────────────────
# API – ORÇAMENTOS
# ─────────────────────────────────────────────

@app.route('/api/orcamentos', methods=['GET'])
@login_required
def api_orcamentos():
    orcamentos = Orcamento.query.order_by(Orcamento.id.desc()).limit(50).all()
    return jsonify([o.to_dict() for o in orcamentos])


@app.route('/api/orcamentos', methods=['POST'])
@login_required
def api_orcamento_criar():
    d = request.get_json()
    orc = Orcamento(
        numero=next_code('ORC', Orcamento, 'numero'),
        usuario_id=session['user_id'],
    )
    db.session.add(orc)
    total = 0
    for item in d.get('itens', []):
        produto = Produto.query.get_or_404(item['produto_id'])
        qtd = float(item['quantidade'])
        preco = float(produto.preco_venda or 0)
        subtotal = qtd * preco
        total += subtotal
        oi = OrcamentoItem(
            orcamento=orc, produto_id=produto.id,
            quantidade=qtd, preco_unitario=preco, total=subtotal
        )
        db.session.add(oi)
    orc.valor_total = total
    db.session.commit()
    return jsonify(orc.to_dict()), 201


# ─────────────────────────────────────────────
# API – BANCO DE DADOS (overview)
# ─────────────────────────────────────────────

@app.route('/api/banco-dados')
@login_required
def api_banco_dados():
    entradas = EntradaEstoque.query.order_by(EntradaEstoque.id.desc()).all()
    saidas = SaidaEstoque.query.order_by(SaidaEstoque.id.desc()).all()
    pedidos = Pedido.query.order_by(Pedido.id.desc()).all()
    orcamentos = Orcamento.query.order_by(Orcamento.id.desc()).all()
    return jsonify({
        'total_entradas': len(entradas),
        'total_saidas': len(saidas),
        'total_pedidos': len(pedidos),
        'total_orcamentos': len(orcamentos),
        'entradas': [e.to_dict() for e in entradas],
        'saidas': [s.to_dict() for s in saidas],
        'pedidos': [p.to_dict() for p in pedidos],
        'orcamentos': [o.to_dict() for o in orcamentos],
    })


# ─────────────────────────────────────────────
# USUÁRIOS (apenas admin)
# ─────────────────────────────────────────────

@app.route('/usuarios')
@admin_required
def usuarios():
    return render_template('usuarios.html')


@app.route('/api/usuarios', methods=['GET'])
@admin_required
def api_usuarios_listar():
    users = Usuario.query.order_by(Usuario.id).all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'nome': u.nome,
        'perfil': u.perfil,
        'ativo': u.ativo,
        'criado_em': u.criado_em.strftime('%d/%m/%Y %H:%M') if u.criado_em else '',
    } for u in users])


@app.route('/api/usuarios', methods=['POST'])
@admin_required
def api_usuario_criar():
    d = request.get_json()
    if not d.get('username') or not d.get('senha'):
        return jsonify({'error': 'Username e senha são obrigatórios'}), 400
    if Usuario.query.filter_by(username=d['username']).first():
        return jsonify({'error': 'Username já existe'}), 400
    u = Usuario(
        username=d['username'],
        nome=d.get('nome', ''),
        perfil=d.get('perfil', 'operador'),
        ativo=True,
    )
    u.set_senha(d['senha'])
    db.session.add(u)
    db.session.commit()
    registrar_log('USUARIO_CRIADO', f'Novo usuário: {u.username} – perfil: {u.perfil}')
    return jsonify({'ok': True}), 201


@app.route('/api/usuarios/<int:uid>', methods=['PUT'])
@admin_required
def api_usuario_editar(uid):
    u = Usuario.query.get_or_404(uid)
    d = request.get_json()
    if 'nome' in d:
        u.nome = d['nome']
    if 'perfil' in d:
        u.perfil = d['perfil']
    if 'ativo' in d:
        u.ativo = d['ativo']
    if d.get('senha'):
        u.set_senha(d['senha'])
    db.session.commit()
    registrar_log('USUARIO_EDITADO', f'Usuário {u.username} – perfil: {u.perfil} – ativo: {u.ativo}')
    return jsonify({'ok': True})


@app.route('/api/usuarios/<int:uid>', methods=['DELETE'])
@admin_required
def api_usuario_deletar(uid):
    if uid == session.get('user_id'):
        return jsonify({'error': 'Você não pode excluir seu próprio usuário'}), 400
    u = Usuario.query.get_or_404(uid)
    u.ativo = False
    db.session.commit()
    registrar_log('USUARIO_DESATIVADO', f'Usuário {u.username} desativado')
    return jsonify({'ok': True})


# ─────────────────────────────────────────────
# AUDIT LOG (apenas admin)
# ─────────────────────────────────────────────

@app.route('/audit-log')
@admin_required
def audit_log_page():
    return render_template('audit_log.html')


@app.route('/api/audit-log', methods=['GET'])
@admin_required
def api_audit_log():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    q = AuditLog.query.order_by(AuditLog.id.desc())

    usuario_filtro = request.args.get('username', '').strip()
    acao_filtro = request.args.get('acao', '').strip()
    if usuario_filtro:
        q = q.filter(AuditLog.username.ilike(f'%{usuario_filtro}%'))
    if acao_filtro:
        q = q.filter(AuditLog.acao.ilike(f'%{acao_filtro}%'))

    total = q.count()
    logs = q.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({
        'total': total,
        'page': page,
        'pages': (total + per_page - 1) // per_page,
        'logs': [l.to_dict() for l in logs],
    })


# ─────────────────────────────────────────────
# INIT DB
# ─────────────────────────────────────────────

def init_db():
    db.create_all()
    if not Usuario.query.filter_by(username='admin').first():
        admin = Usuario(username='admin', nome='Administrador', perfil='admin')
        admin.set_senha('admin123')
        db.session.add(admin)
        db.session.commit()
        print("✅ Usuário admin criado: admin / admin123")


if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
