# app.py
from flask import Flask, jsonify, request, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Create Flask application with custom template folder
app = Flask(__name__,
            template_folder='src/frontend/templates',  # Specify the template directory
            static_folder='src/frontend/static')       # Also specify static files location for consistency

# Configure Flask application
app.config.update(
    DEBUG=True,
    SQLALCHEMY_DATABASE_URI=os.getenv(
        'DATABASE_URL', 'postgresql://localhost/project_catalog'),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SECRET_KEY=os.getenv('SECRET_KEY', 'dev-secret-key')
)

# Initialize database
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Model definition


class Asset(db.Model):
    """Model for storing design asset information"""
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50))
    campaign_name = db.Column(db.String(255))
    client_name = db.Column(db.String(255))
    color_scheme = db.Column(db.String(255))
    theme = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(
    ), onupdate=db.func.current_timestamp())

    def __repr__(self):
        return f'<Asset {self.original_filename}>'


def allowed_file(filename):
    """Validate file extensions"""
    ALLOWED_EXTENSIONS = {'pdf', 'psd', 'ai', 'jpg', 'png'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def home():
    """Display the main page with upload form and search interface"""
    search_query = request.args.get('search', '')

    if search_query:
        assets = Asset.query.filter(
            db.or_(
                Asset.campaign_name.ilike(f'%{search_query}%'),
                Asset.client_name.ilike(f'%{search_query}%'),
                Asset.theme.ilike(f'%{search_query}%')
            )
        ).order_by(Asset.created_at.desc()).all()
    else:
        assets = Asset.query.order_by(Asset.created_at.desc()).all()

    return render_template('index.html', assets=assets, search_query=search_query)


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file uploads"""
    if 'file' not in request.files:
        flash('No file selected')
        return redirect(url_for('home'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected')
        return redirect(url_for('home'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{filename}"

        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))

        asset = Asset(
            filename=unique_filename,
            original_filename=filename,
            file_type=filename.rsplit('.', 1)[1].lower(),
            campaign_name=request.form.get('campaign_name'),
            client_name=request.form.get('client_name'),
            color_scheme=request.form.get('color_scheme'),
            theme=request.form.get('theme')
        )

        db.session.add(asset)
        db.session.commit()

        flash('File uploaded successfully')
        return redirect(url_for('home'))

    flash('Invalid file type')
    return redirect(url_for('home'))


@app.route('/asset/<int:id>')
def asset_detail(id):
    """Display detailed information about a specific asset"""
    asset = Asset.query.get_or_404(id)
    return render_template('asset_detail.html', asset=asset)


if __name__ == '__main__':
    # Debug print to verify template path
    print(f"Template folder: {app.template_folder}")
    # Debug print to verify static path
    print(f"Static folder: {app.static_folder}")
    app.run(debug=True)
