#!/bin/bash

echo "======================================"
echo "PDF Support Verification Script"
echo "======================================"
echo ""

# Check if backend is running
echo "1. Checking Backend Status..."
if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo "   ✅ Backend is running on port 8001"
    curl -s http://localhost:8001/health | grep -q "healthy" && echo "   ✅ Backend is healthy"
else
    echo "   ⚠️  Backend not responding on port 8001"
    echo "   Try starting with: cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8001"
fi
echo ""

# Check Celery worker
echo "2. Checking Celery Worker..."
if ps aux | grep -q "[c]elery.*worker"; then
    echo "   ✅ Celery worker is running"

    # Check if process_pdf task is registered
    if tail -50 /tmp/insightguide-celery.log 2>/dev/null | grep -q "process_pdf"; then
        echo "   ✅ process_pdf task is registered"
    else
        echo "   ⚠️  process_pdf task not found in logs"
    fi
else
    echo "   ⚠️  Celery worker not running"
    echo "   Try starting with: cd backend && source venv/bin/activate && celery -A app.workers.celery_app worker --loglevel=info"
fi
echo ""

# Check poppler installation
echo "3. Checking Poppler Installation..."
if command -v pdfinfo &> /dev/null || command -v /opt/homebrew/bin/pdfinfo &> /dev/null; then
    echo "   ✅ Poppler is installed"
else
    echo "   ⚠️  Poppler not found in PATH"
    echo "   Try: brew install poppler"
fi
echo ""

# Check Python dependencies
echo "4. Checking Python Dependencies..."
cd backend
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate

    if python -c "import PyPDF2" 2>/dev/null; then
        echo "   ✅ PyPDF2 is installed"
    else
        echo "   ⚠️  PyPDF2 not found"
    fi

    if python -c "from pdf2image import convert_from_path" 2>/dev/null; then
        echo "   ✅ pdf2image is installed"
    else
        echo "   ⚠️  pdf2image not found"
    fi

    if python -c "from app.workers.file_conversion_worker import process_pdf" 2>/dev/null; then
        echo "   ✅ process_pdf worker imports successfully"
    else
        echo "   ⚠️  process_pdf worker import failed"
    fi
else
    echo "   ⚠️  Virtual environment not found"
fi
cd ..
echo ""

# Check database
echo "5. Checking Database..."
if docker-compose ps postgres 2>/dev/null | grep -q "Up"; then
    echo "   ✅ PostgreSQL is running"
else
    echo "   ⚠️  PostgreSQL not running"
    echo "   Try: docker-compose up -d postgres"
fi
echo ""

# Check frontend
echo "6. Checking Frontend..."
if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "   ✅ Frontend is running on port 5173"
else
    echo "   ⚠️  Frontend not responding on port 5173"
    echo "   Try: cd frontend && npm run dev"
fi
echo ""

echo "======================================"
echo "Summary"
echo "======================================"
echo ""
echo "Modified Files:"
echo "  - backend/app/core/config.py (added PDF to allowed extensions)"
echo "  - backend/app/workers/file_conversion_worker.py (added process_pdf task)"
echo "  - backend/app/services/deck_service.py (added file type routing)"
echo "  - backend/app/api/routes/decks.py (updated documentation)"
echo "  - frontend/src/routes/DeckUploadPage.tsx (accept .pdf files)"
echo ""
echo "Documentation:"
echo "  - PDF_SUPPORT.md (technical details)"
echo "  - PDF_SUPPORT_GUIDE.md (user guide)"
echo "  - PDF_SUPPORT_SUMMARY.md (implementation summary)"
echo "  - INSTALL_POPPLER.md (installation guide)"
echo ""
echo "Next Steps:"
echo "  1. Ensure all services are running"
echo "  2. Open http://localhost:5173"
echo "  3. Try uploading a PDF file"
echo "  4. Monitor Celery logs: tail -f /tmp/insightguide-celery.log"
echo "  5. Check deck status in database"
echo ""
echo "Test with curl:"
echo "  curl -X POST http://localhost:8001/api/decks \\"
echo "    -F 'file=@test.pdf' \\"
echo "    -F 'title=Test PDF Presentation'"
echo ""
