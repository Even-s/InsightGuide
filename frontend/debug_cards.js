// 在瀏覽器 Console 中運行這個腳本來調試

console.log('=== Topic Cards 診斷工具 ===');

// 檢查當前頁面的狀態
console.log('1. 當前 URL:', window.location.href);

// 嘗試從 localStorage 獲取資料
console.log('2. LocalStorage keys:', Object.keys(localStorage));

// 模擬 API 調用
fetch('http://localhost:8001/api/topic-cards/deck/deck_2730ee69fe11')
  .then(res => res.json())
  .then(cards => {
    console.log('3. API 返回的卡片總數:', cards.length);
    console.log('4. 前 3 張卡片的 slideId:');
    cards.slice(0, 3).forEach((card, i) => {
      console.log(`   卡片 ${i+1}: slideId = ${card.slideId}, title = ${card.title}`);
    });
    
    // 檢查第一張投影片的卡片
    const slide1Cards = cards.filter(c => c.slideId === 'slide_deck_2730ee69fe11_001');
    console.log('5. 第 1 張投影片的卡片數:', slide1Cards.length);
    slide1Cards.forEach(card => {
      console.log(`   - ${card.title}`);
    });
    
    // 檢查是否有 slideId 為 null 的卡片
    const nullSlideCards = cards.filter(c => !c.slideId);
    console.log('6. slideId 為 null 的卡片數:', nullSlideCards.length);
    
    return cards;
  })
  .then(cards => {
    // 檢查 React Dev Tools
    console.log('7. 如果您安裝了 React DevTools，請檢查 EditorPage 組件的 state:');
    console.log('   - slides 陣列是否有資料？');
    console.log('   - cards 陣列是否有資料？');
    console.log('   - selectedSlideId 是什麼？');
  })
  .catch(err => {
    console.error('API 調用失敗:', err);
  });

console.log('\n請在上面的輸出中查找問題！');
