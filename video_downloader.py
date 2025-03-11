import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urljoin
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import json

def scroll_to_bottom(driver):
    """滚动到页面底部以触发懒加载"""
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)

def get_video_url_from_page_source(html_content):
    """从页面源码中提取视频URL"""
    try:
        # 尝试查找包含视频信息的JSON数据
        soup = BeautifulSoup(html_content, 'html.parser')
        scripts = soup.find_all('script')
        
        for script in scripts:
            content = script.string
            if content and 'videoUrl' in content:
                # 尝试解析JSON数据
                try:
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    if start >= 0 and end > start:
                        json_str = content[start:end]
                        data = json.loads(json_str)
                        
                        # 查找可能包含视频URL的字段
                        if isinstance(data, dict):
                            for key, value in data.items():
                                if isinstance(value, str) and ('mp4' in value or 'video' in value):
                                    return value
                except:
                    continue
    except:
        pass
    return None

def download_video(url, save_dir='downloads', index=None):
    """
    从指定网页下载视频
    
    Args:
        url (str): 网页地址
        save_dir (str): 保存视频的目录
        index (int): 当前下载的序号
    """
    try:
        # 创建保存目录
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        
        task_info = f"任务 {index}: " if index is not None else ""
        print(f"\n{task_info}开始处理: {url}")
        
        # 配置Chrome选项
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # 无界面模式
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-web-security')  # 禁用同源策略
        chrome_options.add_argument('--disable-features=IsolateOrigins,site-per-process')  # 允许跨域iframe
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        
        print(f"{task_info}正在访问网页...")
        # 初始化WebDriver
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)  # 设置页面加载超时时间
        
        try:
            # 访问页面
            driver.get(url)
            time.sleep(5)  # 等待页面初始加载
            
            # 滚动页面以触发懒加载
            scroll_to_bottom(driver)
            
            # 尝试多种方法获取视频URL
            video_url = None
            
            # 方法1: 直接查找video标签
            try:
                wait = WebDriverWait(driver, 10)
                video_elements = wait.until(
                    EC.presence_of_all_elements_located((By.TAG_NAME, "video"))
                )
                if video_elements:
                    video_url = video_elements[0].get_attribute('src')
            except TimeoutException:
                print(f"{task_info}未找到video标签，尝试其他方法...")
            
            # 方法2: 检查所有iframe
            if not video_url:
                iframes = driver.find_elements(By.TAG_NAME, "iframe")
                for iframe in iframes:
                    try:
                        driver.switch_to.frame(iframe)
                        video_elements = driver.find_elements(By.TAG_NAME, "video")
                        if video_elements:
                            video_url = video_elements[0].get_attribute('src')
                            driver.switch_to.default_content()
                            break
                        driver.switch_to.default_content()
                    except:
                        driver.switch_to.default_content()
                        continue
            
            # 方法3: 从页面源码中提取
            if not video_url:
                video_url = get_video_url_from_page_source(driver.page_source)
            
            if not video_url:
                print(f"{task_info}未找到视频链接")
                return False
            
            # 处理视频URL
            if video_url.startswith('//'):
                video_url = 'https:' + video_url
            elif not video_url.startswith(('http://', 'https://')):
                video_url = urljoin(url, video_url)
            
            print(f"{task_info}找到视频链接: {video_url}")
            
            # 设置请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': url,
                'Range': 'bytes=0-'  # 支持断点续传
            }
            
            # 下载视频
            print(f"{task_info}正在下载视频...")
            video_response = requests.get(video_url, headers=headers, stream=True)
            video_response.raise_for_status()
            
            # 生成文件名
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            index_str = f"_{index}" if index is not None else ""
            filename = f"video_{timestamp}{index_str}.mp4"
            filepath = os.path.join(save_dir, filename)
            
            # 保存视频文件
            total_size = int(video_response.headers.get('content-length', 0))
            block_size = 1024  # 1 KB
            downloaded_size = 0
            
            with open(filepath, 'wb') as f:
                for chunk in video_response.iter_content(chunk_size=block_size):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        # 显示下载进度
                        if total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            print(f"\r{task_info}下载进度: {progress:.2f}%", end='')
            
            print(f"\n{task_info}视频已保存到: {filepath}")
            print(f"{task_info}下载完成！")
            return True
            
        finally:
            driver.quit()
        
    except Exception as e:
        print(f"{task_info}发生错误: {e}")
        return False

def process_url_file(url_file, save_dir='downloads'):
    """
    从文件读取URL并按顺序下载视频
    
    Args:
        url_file (str): 包含URL的文件路径
        save_dir (str): 保存视频的目录
    """
    try:
        # 检查URL文件是否存在
        if not os.path.exists(url_file):
            print(f"错误: URL文件 '{url_file}' 不存在")
            return
        
        # 读取并过滤URL列表
        with open(url_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
        
        total_urls = len(urls)
        if total_urls == 0:
            print("URL文件为空")
            return
        
        print(f"共找到 {total_urls} 个URL")
        
        # 创建进度文件
        progress_file = os.path.join(save_dir, 'download_progress.txt')
        
        # 读取已完成的任务
        completed_tasks = set()
        if os.path.exists(progress_file):
            with open(progress_file, 'r', encoding='utf-8') as f:
                completed_tasks = set(int(line.strip()) for line in f if line.strip().isdigit())
        
        # 处理每个URL
        for i, url in enumerate(urls, 1):
            if i in completed_tasks:
                print(f"\n任务 {i}/{total_urls}: 已完成，跳过")
                continue
                
            print(f"\n开始处理任务 {i}/{total_urls}")
            success = download_video(url, save_dir, i)
            
            # 记录成功的任务
            if success:
                with open(progress_file, 'a', encoding='utf-8') as f:
                    f.write(f"{i}\n")
        
        print("\n所有任务处理完成！")
        
    except Exception as e:
        print(f"处理URL文件时发生错误: {e}")

def main():
    # 获取用户输入
    url_file = input("请输入包含URL的文件路径: ").strip()
    save_dir = input("请输入保存目录（直接回车使用默认目录 'downloads'）: ").strip() or 'downloads'
    
    # 处理URL文件
    process_url_file(url_file, save_dir)

if __name__ == "__main__":
    main() 